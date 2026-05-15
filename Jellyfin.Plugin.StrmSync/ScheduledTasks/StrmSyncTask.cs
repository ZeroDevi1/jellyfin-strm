using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.StrmSync.StrmSync;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.StrmSync.ScheduledTasks;

/// <summary>
/// Scheduled task for full STRM sync.
/// </summary>
public class StrmSyncTask : IScheduledTask
{
    private readonly ILogger<StrmSyncTask> _logger;

    /// <summary>
    /// Initializes a new instance of the <see cref="StrmSyncTask"/> class.
    /// </summary>
    /// <param name="logger">Logger instance.</param>
    public StrmSyncTask(ILogger<StrmSyncTask> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public string Name => "115 STRM 全量同步";

    /// <inheritdoc />
    public string Key => "StrmSync";

    /// <inheritdoc />
    public string Description => "扫描影子库中的所有 .nfo 文件，为缺失的视频生成 .strm 链接。";

    /// <inheritdoc />
    public string Category => "Library";

    /// <inheritdoc />
    public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
    {
        return new[]
        {
            new TaskTriggerInfo
            {
                Type = TaskTriggerInfo.TriggerDaily,
                TimeOfDayTicks = TimeSpan.FromHours(2).Ticks,
                MaxRuntimeTicks = TimeSpan.FromHours(4).Ticks
            }
        };
    }

    /// <inheritdoc />
    public Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null)
        {
            _logger.LogWarning("Plugin configuration is not available.");
            return Task.CompletedTask;
        }

        if (string.IsNullOrWhiteSpace(config.SourceRoot) || string.IsNullOrWhiteSpace(config.ShadowRoot))
        {
            _logger.LogWarning("SourceRoot or ShadowRoot is not configured.");
            return Task.CompletedTask;
        }

        var generator = new StrmGenerator(_logger);
        var summary = generator.Sync(config, dryRun: false);

        if (summary.HasChanges && config.JellyfinEnabled)
        {
            var stateDir = Path.Combine(config.ShadowRoot, ".jellyfin-strm-state");
            var refresher = new LibraryRefresher(_logger);
            refresher.MaybeRefreshAsync(config, true, stateDir).ConfigureAwait(false).GetAwaiter().GetResult();
        }

        progress.Report(100.0);
        return Task.CompletedTask;
    }
}
