using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Jellyfin.Plugin.StrmSync.Configuration;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.StrmSync.StrmSync;

/// <summary>
/// Represents a planned STRM file write.
/// </summary>
public class PlannedWrite
{
    /// <summary>
    /// Gets or sets the relative path.
    /// </summary>
    public string RelativePath { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the STRM content.
    /// </summary>
    public string Content { get; set; } = string.Empty;
}

/// <summary>
/// Represents a planned sidecar file copy.
/// </summary>
public class PlannedCopy
{
    /// <summary>
    /// Gets or sets the relative path.
    /// </summary>
    public string RelativePath { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the source path.
    /// </summary>
    public string SourcePath { get; set; } = string.Empty;
}

/// <summary>
/// Summary of sync execution.
/// </summary>
public class ExecutionSummary
{
    /// <summary>
    /// Gets or sets the number of written STRM files.
    /// </summary>
    public int WrittenStrms { get; set; }

    /// <summary>
    /// Gets or sets the number of copied sidecar files.
    /// </summary>
    public int CopiedFiles { get; set; }

    /// <summary>
    /// Gets or sets the number of deleted paths.
    /// </summary>
    public int DeletedPaths { get; set; }

    /// <summary>
    /// Gets or sets a value indicating whether this was a dry run.
    /// </summary>
    public bool DryRun { get; set; }

    /// <summary>
    /// Gets a value indicating whether any changes were made.
    /// </summary>
    public bool HasChanges => WrittenStrms + CopiedFiles + DeletedPaths > 0;
}

/// <summary>
/// STRM file generator engine.
/// </summary>
public class StrmGenerator
{
    private readonly ILogger _logger;

    /// <summary>
    /// Initializes a new instance of the <see cref="StrmGenerator"/> class.
    /// </summary>
    /// <param name="logger">Logger instance.</param>
    public StrmGenerator(ILogger logger)
    {
        _logger = logger;
    }

    /// <summary>
    /// Builds a sync plan without executing it.
    /// </summary>
    /// <param name="config">Plugin configuration.</param>
    /// <returns>List of planned writes.</returns>
    public List<PlannedWrite> BuildSyncPlan(PluginConfiguration config)
    {
        var sourceRoot = new DirectoryInfo(config.SourceRoot);
        var shadowRoot = new DirectoryInfo(config.ShadowRoot);
        var plan = new List<PlannedWrite>();

        if (!sourceRoot.Exists)
        {
            _logger.LogWarning("Source root does not exist: {SourceRoot}", config.SourceRoot);
            return plan;
        }

        if (!shadowRoot.Exists)
        {
            _logger.LogInformation("Shadow root does not exist: {ShadowRoot}", config.ShadowRoot);
            return plan;
        }

        var nfoFiles = FindNfoFiles(shadowRoot, config);
        foreach (var nfoPath in nfoFiles)
        {
            if (HasStrmForNfo(nfoPath))
            {
                continue;
            }

            var relativeDir = GetRelativePath(nfoPath.DirectoryName!, shadowRoot.FullName);
            var sourceDir = new DirectoryInfo(Path.Combine(sourceRoot.FullName, relativeDir));

            var videoPath = FindVideoForNfo(nfoPath, sourceDir, config);
            if (videoPath == null)
            {
                _logger.LogWarning("No matching video found for NFO: {NfoPath}", nfoPath.FullName);
                continue;
            }

            var videoRelative = GetRelativePath(videoPath.FullName, sourceRoot.FullName).Replace('\\', '/');
            var strmRelative = Path.ChangeExtension(videoRelative, ".strm");
            var content = $"{config.StrmPrefix.TrimEnd('/')}/{videoRelative}";

            plan.Add(new PlannedWrite
            {
                RelativePath = strmRelative,
                Content = content
            });
        }

        return plan;
    }

    /// <summary>
    /// Executes the sync plan.
    /// </summary>
    /// <param name="config">Plugin configuration.</param>
    /// <param name="plan">Sync plan.</param>
    /// <param name="dryRun">Whether to perform a dry run.</param>
    /// <returns>Execution summary.</returns>
    public ExecutionSummary ExecutePlan(PluginConfiguration config, List<PlannedWrite> plan, bool dryRun)
    {
        var summary = new ExecutionSummary { DryRun = dryRun };
        var shadowRoot = new DirectoryInfo(config.ShadowRoot);
        shadowRoot.Create();

        foreach (var item in plan)
        {
            var targetPath = new FileInfo(Path.Combine(shadowRoot.FullName, item.RelativePath));
            targetPath.Directory?.Create();

            if (dryRun)
            {
                _logger.LogInformation("[DRY-RUN] Would write STRM: {TargetPath}", targetPath.FullName);
                summary.WrittenStrms++;
                continue;
            }

            try
            {
                File.WriteAllText(targetPath.FullName, item.Content + Environment.NewLine, Encoding.UTF8);
                summary.WrittenStrms++;
                _logger.LogInformation("Wrote STRM: {TargetPath}", targetPath.FullName);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to write STRM: {TargetPath}", targetPath.FullName);
            }
        }

        return summary;
    }

    /// <summary>
    /// Performs a full sync.
    /// </summary>
    /// <param name="config">Plugin configuration.</param>
    /// <param name="dryRun">Whether to perform a dry run.</param>
    /// <returns>Execution summary.</returns>
    public ExecutionSummary Sync(PluginConfiguration config, bool dryRun = false)
    {
        _logger.LogInformation("Starting STRM sync. Source={SourceRoot}, Shadow={ShadowRoot}", config.SourceRoot, config.ShadowRoot);
        var plan = BuildSyncPlan(config);
        _logger.LogInformation("Sync plan: {Count} STRM files to write", plan.Count);
        var summary = ExecutePlan(config, plan, dryRun);
        _logger.LogInformation(
            "Sync complete. WrittenStrms={WrittenStrms}, CopiedFiles={CopiedFiles}, DeletedPaths={DeletedPaths}",
            summary.WrittenStrms,
            summary.CopiedFiles,
            summary.DeletedPaths);
        return summary;
    }

    /// <summary>
    /// Builds a directory snapshot for change detection.
    /// </summary>
    /// <param name="shadowRoot">Shadow root directory.</param>
    /// <returns>Snapshot digest string.</returns>
    public string BuildSnapshot(string shadowRoot)
    {
        var dir = new DirectoryInfo(shadowRoot);
        if (!dir.Exists)
        {
            return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Empty)));
        }

        var entries = new List<string>();
        foreach (var subDir in dir.GetDirectories("*", SearchOption.AllDirectories))
        {
            var rel = GetRelativePath(subDir.FullName, shadowRoot).Replace('\\', '/');
            entries.Add($"dir:{rel}:{subDir.LastWriteTimeUtc:O}");
        }

        foreach (var file in dir.GetFiles("*.strm", SearchOption.AllDirectories))
        {
            var rel = GetRelativePath(file.FullName, shadowRoot).Replace('\\', '/');
            entries.Add($"strm:{rel}:{file.Length}:{file.LastWriteTimeUtc:O}");
        }

        entries.Sort(StringComparer.Ordinal);
        var text = string.Join("\n", entries);
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    }

    private static List<FileInfo> FindNfoFiles(DirectoryInfo root, PluginConfiguration config)
    {
        var result = new List<FileInfo>();
        foreach (var file in root.GetFiles("*.nfo", SearchOption.AllDirectories))
        {
            var relDir = GetRelativePath(file.DirectoryName!, root.FullName);
            if (ShouldSkipDirectory(relDir, config))
            {
                continue;
            }

            result.Add(file);
        }

        return result;
    }

    private static bool HasStrmForNfo(FileInfo nfoPath)
    {
        var strmPath = Path.ChangeExtension(nfoPath.FullName, ".strm");
        return File.Exists(strmPath);
    }

    private static FileInfo? FindVideoForNfo(FileInfo nfoPath, DirectoryInfo sourceDir, PluginConfiguration config)
    {
        if (!sourceDir.Exists)
        {
            return null;
        }

        var nfoStem = Path.GetFileNameWithoutExtension(nfoPath.Name).ToLowerInvariant();
        foreach (var file in sourceDir.GetFiles())
        {
            if (IsVideoFile(file.Name, config))
            {
                var videoStem = Path.GetFileNameWithoutExtension(file.Name).ToLowerInvariant();
                if (videoStem == nfoStem)
                {
                    return file;
                }
            }
        }

        return null;
    }

    private static bool IsVideoFile(string fileName, PluginConfiguration config)
    {
        var ext = Path.GetExtension(fileName).ToLowerInvariant();
        return config.VideoExtensions.Contains(ext, StringComparer.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipDirectory(string relativePath, PluginConfiguration config)
    {
        var parts = relativePath.Split(new[] { '/', '\\' }, StringSplitOptions.RemoveEmptyEntries);
        return parts.Any(part =>
            config.ExcludeDirectories.Contains(part, StringComparer.OrdinalIgnoreCase));
    }

    private static string GetRelativePath(string fullPath, string basePath)
    {
        if (!basePath.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal))
        {
            basePath += Path.DirectorySeparatorChar;
        }

        var full = Path.GetFullPath(fullPath);
        var baseFull = Path.GetFullPath(basePath);
        if (full.StartsWith(baseFull, StringComparison.OrdinalIgnoreCase))
        {
            return full[baseFull.Length..];
        }

        return fullPath;
    }
}
