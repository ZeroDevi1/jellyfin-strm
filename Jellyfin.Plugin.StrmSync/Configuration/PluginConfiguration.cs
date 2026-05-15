using System;
using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.StrmSync.Configuration;

/// <summary>
/// Plugin configuration.
/// </summary>
public class PluginConfiguration : BasePluginConfiguration
{
    /// <summary>
    /// Initializes a new instance of the <see cref="PluginConfiguration" /> class.
    /// </summary>
    public PluginConfiguration()
    {
        SourceRoot = string.Empty;
        ShadowRoot = string.Empty;
        StrmPrefix = string.Empty;
        VideoExtensions = new[] { ".mp4", ".mkv", ".avi", ".ts", ".m2ts", ".mov" };
        SidecarExtensions = new[] { ".nfo", ".jpg", ".jpeg", ".png", ".webp", ".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".txt" };
        SidecarNamePatterns = new[] { "poster", "fanart", "thumb", "clearlogo", "logo", "banner", "landscape", "disc", "keyart" };
        PreserveDirectories = new[] { "behind the scenes", "extrafanart", "extrathumbs", "featurettes", "deleted scenes", "trailers" };
        ExcludeDirectories = new[] { ".mount-health", ".@__thumb", "@eadir", "$recycle.bin", "system volume information", ".ds_store", "thumbs.db" };
        DeleteRatioLimit = 0.25;
        DeleteCountLimit = 20;
        WatchEnabled = true;
        WatchIntervalSeconds = 30;
        JellyfinEnabled = false;
        JellyfinServerUrl = string.Empty;
        JellyfinApiKey = string.Empty;
        JellyfinLibraryName = "115strm";
        JellyfinDebounceSeconds = 600;
    }

    /// <summary>
    /// Gets or sets the source root path (CloudDrive mount).
    /// </summary>
    public string SourceRoot { get; set; }

    /// <summary>
    /// Gets or sets the shadow root path (local STRM library).
    /// </summary>
    public string ShadowRoot { get; set; }

    /// <summary>
    /// Gets or sets the STRM prefix path (path visible inside Jellyfin container).
    /// </summary>
    public string StrmPrefix { get; set; }

    /// <summary>
    /// Gets or sets the video file extensions.
    /// </summary>
    public string[] VideoExtensions { get; set; }

    /// <summary>
    /// Gets or sets the sidecar file extensions.
    /// </summary>
    public string[] SidecarExtensions { get; set; }

    /// <summary>
    /// Gets or sets the sidecar name patterns.
    /// </summary>
    public string[] SidecarNamePatterns { get; set; }

    /// <summary>
    /// Gets or sets the preserve directories.
    /// </summary>
    public string[] PreserveDirectories { get; set; }

    /// <summary>
    /// Gets or sets the exclude directories.
    /// </summary>
    public string[] ExcludeDirectories { get; set; }

    /// <summary>
    /// Gets or sets the delete ratio limit.
    /// </summary>
    public double DeleteRatioLimit { get; set; }

    /// <summary>
    /// Gets or sets the delete count limit.
    /// </summary>
    public int DeleteCountLimit { get; set; }

    /// <summary>
    /// Gets or sets a value indicating whether file watcher is enabled.
    /// </summary>
    public bool WatchEnabled { get; set; }

    /// <summary>
    /// Gets or sets the watch interval in seconds.
    /// </summary>
    public int WatchIntervalSeconds { get; set; }

    /// <summary>
    /// Gets or sets a value indicating whether Jellyfin refresh is enabled.
    /// </summary>
    public bool JellyfinEnabled { get; set; }

    /// <summary>
    /// Gets or sets the Jellyfin server URL.
    /// </summary>
    public string JellyfinServerUrl { get; set; }

    /// <summary>
    /// Gets or sets the Jellyfin API key.
    /// </summary>
    public string JellyfinApiKey { get; set; }

    /// <summary>
    /// Gets or sets the Jellyfin library name.
    /// </summary>
    public string JellyfinLibraryName { get; set; }

    /// <summary>
    /// Gets or sets the Jellyfin refresh debounce seconds.
    /// </summary>
    public int JellyfinDebounceSeconds { get; set; }
}
