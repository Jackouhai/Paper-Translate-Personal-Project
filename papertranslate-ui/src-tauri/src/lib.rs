use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let project_root =
                std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("../..")
                    .canonicalize()?;

            let python_path = project_root.join(".venv/bin/python");
            let backend_dir = project_root.join("backend");
            let launcher_path = backend_dir.join("run_backend.py");

            let child = Command::new(python_path)
                .arg(launcher_path)
                .current_dir(backend_dir)
                .spawn()?;

            let state = app.state::<BackendProcess>();
            *state.0.lock().unwrap() = Some(child);

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<BackendProcess>();

                let mut process = state
                    .0
                    .lock()
                    .expect("failed to lock backend process");

                if let Some(mut child) = process.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running PaperTranslate");
}

