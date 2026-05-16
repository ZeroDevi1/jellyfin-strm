using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.StrmSync.StrmSync;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.StrmSync.Services;

/// <summary>
/// Background service that watches the shadow root for changes and triggers sync.
/// </summary>
public class FileWatcherService : IHostedService, IDisposable
{
    private readonly ILogger<FileWatcherService> _logger;
    private Task? _executeTask;
    private CancellationTokenSource? _stoppingCts;
    private string _lastSnapshot = string.Empty;

    /// <summary>
    /// Gets a value indicating whether the watcher service is currently running.
    /// </summary>
    public static bool IsRunning { get; private set; }

    /// <summary>
    /// Initializes a new instance of the <see cref="FileWatcherService"/> class.
    /// </summary>
    /// <param name="logger">Logger instance.</param>
    public FileWatcherService(ILogger<FileWatcherService> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public Task StartAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("STRM file watcher service starting.");
        IsRunning = true;
        var config = Plugin.Instance?.Configuration;
        if (config != null)
        {
            config.IsWatcherRunning = true;
        }

        _stoppingCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _executeTask = ExecuteAsync(_stoppingCts.Token);
        return _executeTask.IsCompleted ? _executeTask : Task.CompletedTask;
    }

    /// <inheritdoc />
    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("STRM file watcher service stopping.");
        IsRunning = false;
        var config = Plugin.Instance?.Configuration;
        if (config != null)
        {
            config.IsWatcherRunning = false;
        }

        if (_stoppingCts is null)
        {
            return;
        }

        _stoppingCts.Cancel();
        if (_executeTask != null)
        {
            await Task.WhenAny(_executeTask, Task.Delay(Timeout.Infinite, cancellationToken)).ConfigureAwait(false);
        }
    }

    /// <inheritdoc />
    public void Dispose()
    {
        _stoppingCts?.Cancel();
        _stoppingCts?.Dispose();
        GC.SuppressFinalize(this);
    }

    private async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var config = Plugin.Instance?.Configuration;
            if (config != null && config.WatchEnabled && !string.IsNullOrWhiteSpace(config.SourceRoot) && !string.IsNullOrWhiteSpace(config.ShadowRoot))
            {
                try
                {
                    var generator = new StrmGenerator(_logger);
                    var currentSnapshot = generator.BuildSnapshot(config.ShadowRoot);

                    if (!string.Equals(_lastSnapshot, currentSnapshot, StringComparison.Ordinal))
                    {
                        _logger.LogInformation("Shadow directory changed, triggering sync.");
                        var summary = generator.Sync(config, dryRun: false);

                        config.LastSyncTime = DateTime.UtcNow;
                        config.LastSyncResult = $"STRM: {summary.WrittenStrms}, Copied: {summary.CopiedFiles}, Deleted: {summary.DeletedPaths}";

                        if (!string.IsNullOrWhiteSpace(config.ShadowRoot) && Directory.Exists(config.ShadowRoot))
                        {
                            config.TotalStrmCount = Directory.GetFiles(config.ShadowRoot, "*.strm", SearchOption.AllDirectories).Length;
                        }

                        if (summary.HasChanges && config.JellyfinEnabled)
                        {
                            var stateDir = Path.Combine(config.ShadowRoot, ".jellyfin-strm-state");
                            var refresher = new LibraryRefresher(_logger);
                            await refresher.MaybeRefreshAsync(config, true, stateDir).ConfigureAwait(false);
                        }

                        _lastSnapshot = currentSnapshot;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error during watch sync iteration.");
                }
            }

            var interval = config?.WatchIntervalSeconds ?? 30;
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(interval), stoppingToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }
}
