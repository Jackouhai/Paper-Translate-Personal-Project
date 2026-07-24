use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

struct BackendProcess(Mutex<Option<Child>>);

fn start_backend(app: &tauri::App) -> Result<Child, Box<dyn std::error::Error>> {
    let backend_executable = if cfg!(debug_assertions) {
        // Khi chạy npx tauri dev
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("binaries")
            .join("papertranslate-backend")
            .join("papertranslate-backend")
    } else {
        // Khi chạy AppImage, .deb hoặc .rpm
        app.path()
            .resource_dir()?
            .join("binaries")
            .join("papertranslate-backend")
            .join("papertranslate-backend")
    };

    if !backend_executable.exists() {
        return Err(
            format!(
                "Backend executable was not found: {}",
                backend_executable.display()
            )
            .into(),
        );
    }

    let backend_dir = backend_executable
        .parent()
        .ok_or("Backend directory was not found")?;

    let child = Command::new(&backend_executable)
        .current_dir(backend_dir)
        .spawn()?;

    Ok(child)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let child = start_backend(app)?;

            let state = app.state::<BackendProcess>();
            *state
                .0
                .lock()
                .expect("failed to lock backend process") = Some(child);

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building PaperTranslate");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            let state = app_handle.state::<BackendProcess>();

            let mut process = state
                .0
                .lock()
                .expect("failed to lock backend process");

            if let Some(mut child) = process.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    });
}