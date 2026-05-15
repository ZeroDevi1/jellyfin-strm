using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.StrmSync.Configuration;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.StrmSync.StrmSync;

/// <summary>
/// Jellyfin library refresh helper.
/// </summary>
public class LibraryRefresher
{
    private readonly ILogger _logger;

    /// <summary>
    /// Initializes a new instance of the <see cref="LibraryRefresher"/> class.
    /// </summary>
    /// <param name="logger">Logger instance.</param>
    public LibraryRefresher(ILogger logger)
    {
        _logger = logger;
    }

    /// <summary>
    /// Requests a Jellyfin library refresh if conditions are met.
    /// </summary>
    /// <param name="config">Plugin configuration.</param>
    /// <param name="hasChanges">Whether the sync made changes.</param>
    /// <param name="stateDir">State directory for debounce tracking.</param>
    /// <returns>A <see cref="Task"/> representing the asynchronous operation.</returns>
    public async Task MaybeRefreshAsync(PluginConfiguration config, bool hasChanges, string stateDir)
    {
        if (!hasChanges || !config.JellyfinEnabled)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(config.JellyfinServerUrl) || string.IsNullOrWhiteSpace(config.JellyfinApiKey))
        {
            _logger.LogWarning("Jellyfin refresh is enabled but server URL or API key is missing.");
            return;
        }

        var stateFile = Path.Combine(stateDir, "jellyfin-refresh-state.json");
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

        if (!ShouldRefresh(stateFile, config.JellyfinLibraryName, now, config.JellyfinDebounceSeconds))
        {
            _logger.LogInformation("Jellyfin refresh skipped due to debounce window.");
            return;
        }

        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
            var request = new HttpRequestMessage(HttpMethod.Post, $"{config.JellyfinServerUrl.TrimEnd('/')}/Library/Refresh")
            {
                Content = new StringContent("{}", Encoding.UTF8, "application/json")
            };
            request.Headers.Add("X-Emby-Token", config.JellyfinApiKey);

            var response = await client.SendAsync(request, CancellationToken.None).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();

            MarkRefreshed(stateFile, config.JellyfinLibraryName, now);
            _logger.LogInformation("Requested Jellyfin library refresh for {LibraryName}", config.JellyfinLibraryName);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to request Jellyfin library refresh.");
        }
    }

    private static bool ShouldRefresh(string stateFile, string libraryName, long now, int debounceSeconds)
    {
        var state = LoadState(stateFile);
        if (state.TryGetValue(libraryName, out var lastRefreshed))
        {
            return (now - lastRefreshed) >= debounceSeconds;
        }

        return true;
    }

    private static void MarkRefreshed(string stateFile, string libraryName, long at)
    {
        var state = LoadState(stateFile);
        state[libraryName] = at;
        var dir = Path.GetDirectoryName(stateFile);
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
        }

        File.WriteAllText(stateFile, JsonSerializer.Serialize(state, new JsonSerializerOptions { WriteIndented = true }));
    }

    private static System.Collections.Generic.Dictionary<string, long> LoadState(string stateFile)
    {
        if (!File.Exists(stateFile))
        {
            return new System.Collections.Generic.Dictionary<string, long>();
        }

        try
        {
            var text = File.ReadAllText(stateFile);
            return JsonSerializer.Deserialize<System.Collections.Generic.Dictionary<string, long>>(text)
                ?? new System.Collections.Generic.Dictionary<string, long>();
        }
        catch
        {
            return new System.Collections.Generic.Dictionary<string, long>();
        }
    }
}
