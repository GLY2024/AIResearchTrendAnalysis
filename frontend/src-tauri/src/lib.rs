use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .setup(|app| {
            // Use resource_dir (same as exe dir for portable builds)
            let sidecar_data_dir = app
                .path()
                .resource_dir()
                .map(|d| d.join("ddata"))
                .ok()
                .or_else(|| app.path().app_local_data_dir().ok());

            // Launch the Python backend sidecar
            let sidecar_command = match app.shell().sidecar("binaries/arta-backend") {
                Ok(cmd) => cmd,
                Err(e) => {
                    log::error!("Failed to create sidecar command: {}", e);
                    return Ok(());
                }
            };

            let sidecar_command = if let Some(data_dir) = &sidecar_data_dir {
                if let Err(e) = std::fs::create_dir_all(data_dir) {
                    log::warn!("Failed to prepare backend data directory {:?}: {}", data_dir, e);
                    sidecar_command
                } else {
                    // Strip \\?\ prefix — Python's sqlite3 cannot handle UNC extended paths
                    let dir_str = data_dir.to_string_lossy().to_string();
                    let clean = dir_str.strip_prefix(r"\\?\").unwrap_or(&dir_str).to_string();
                    sidecar_command.env("ARTA_DATA_DIR", clean)
                }
            } else {
                log::warn!("Falling back to sidecar-default data directory");
                sidecar_command
            };

            match sidecar_command.spawn() {
                Ok((mut rx, _child)) => {
                    log::info!("ARTA backend sidecar started");
                    // Log sidecar output in background
                    tauri::async_runtime::spawn(async move {
                        use tauri_plugin_shell::process::CommandEvent;
                        while let Some(event) = rx.recv().await {
                            match event {
                                CommandEvent::Stdout(line) => {
                                    log::info!("[sidecar stdout] {}", String::from_utf8_lossy(&line));
                                }
                                CommandEvent::Stderr(line) => {
                                    log::warn!("[sidecar stderr] {}", String::from_utf8_lossy(&line));
                                }
                                CommandEvent::Terminated(payload) => {
                                    log::error!("[sidecar] terminated with code: {:?}, signal: {:?}", payload.code, payload.signal);
                                    break;
                                }
                                CommandEvent::Error(err) => {
                                    log::error!("[sidecar] error: {}", err);
                                    break;
                                }
                                _ => {}
                            }
                        }
                    });
                }
                Err(e) => {
                    log::error!("Failed to spawn sidecar: {}", e);
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
