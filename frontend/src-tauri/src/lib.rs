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
            // Launch the Python backend sidecar
            let sidecar_command = match app.shell().sidecar("binaries/arta-backend") {
                Ok(cmd) => cmd,
                Err(e) => {
                    log::error!("Failed to create sidecar command: {}", e);
                    // Continue without backend - user can start it manually
                    return Ok(());
                }
            };

            match sidecar_command.spawn() {
                Ok((_rx, _child)) => {
                    log::info!("ARTA backend sidecar started");
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
