use tauri::{path::BaseDirectory, Manager};
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
            let sidecar_data_dir = app
                .path()
                .resolve("data", BaseDirectory::Executable)
                .ok()
                .filter(|path| path.exists())
                .or_else(|| app.path().app_local_data_dir().ok());

            // Launch the Python backend sidecar
            let sidecar_command = match app.shell().sidecar("binaries/arta-backend") {
                Ok(cmd) => cmd,
                Err(e) => {
                    log::error!("Failed to create sidecar command: {}", e);
                    // Continue without backend - user can start it manually
                    return Ok(());
                }
            };

            let sidecar_command = if let Some(data_dir) = sidecar_data_dir {
                if let Err(e) = std::fs::create_dir_all(&data_dir) {
                    log::warn!("Failed to prepare backend data directory {:?}: {}", data_dir, e);
                    sidecar_command
                } else {
                    sidecar_command.env("ARTA_DATA_DIR", data_dir)
                }
            } else {
                log::warn!("Falling back to sidecar-default data directory");
                sidecar_command
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
