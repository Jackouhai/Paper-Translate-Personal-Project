use std::{
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
};

use tauri::{Manager, RunEvent};

struct BackendProcess(Mutex<Option<Child>>);

#[allow(unused_variables)]
fn start_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    let (python_path, backend_script, working_dir): (PathBuf, PathBuf, PathBuf);

    #[cfg(debug_assertions)]
    {
        // CARGO_MANIFEST_DIR:
        // <project>/papertranslate-ui/src-tauri
        let tauri_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));

        let project_root = tauri_dir
            .join("../..")
            .canonicalize()
            .map_err(|error| format!("Could not resolve project root: {error}"))?;

        python_path = project_root
            .join("desktop-runtime")
            .join("venv")
            .join("bin")
            .join("python");

        backend_script = project_root.join("backend").join("run_backend.py");

        working_dir = project_root.join("backend");
    }

    #[cfg(not(debug_assertions))]
    {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| format!("Could not resolve Tauri resource directory: {error}"))?;

        python_path = resource_dir
            .join("runtime")
            .join("venv")
            .join("bin")
            .join("python");

        backend_script = resource_dir.join("backend-app").join("run_backend.py");

        working_dir = resource_dir.join("backend-app");
    }

    if !python_path.exists() {
        return Err(format!(
            "Bundled Python executable was not found: {}",
            python_path.display()
        ));
    }

    if !backend_script.exists() {
        return Err(format!(
            "Backend launcher was not found: {}",
            backend_script.display()
        ));
    }

    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("Could not resolve app data directory: {error}"))?;

    std::fs::create_dir_all(&app_data_dir)
        .map_err(|error| format!("Could not create app data directory: {error}"))?;

    println!("Starting backend with Python: {}", python_path.display());
    println!("Backend script: {}", backend_script.display());
    println!("App data directory: {}", app_data_dir.display());

    Command::new(&python_path)
        .arg(&backend_script)
        .current_dir(&working_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PAPERTRANSLATE_DATA_DIR", &app_data_dir)
        .spawn()
        .map_err(|error| format!("Failed to start bundled Python backend: {error}"))
}

fn stop_backend(app_handle: &tauri::AppHandle) {
    let backend_state = app_handle.state::<BackendProcess>();

    let Ok(mut process_guard) = backend_state.0.lock() else {
        eprintln!("Could not lock backend process state.");
        return;
    };

    if let Some(mut child) = process_guard.take() {
        if let Err(error) = child.kill() {
            eprintln!("Failed to stop backend process: {error}");
        }

        if let Err(error) = child.wait() {
            eprintln!("Failed to wait for backend process: {error}");
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::new().build())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let backend_process = start_backend(&app.handle())
                .map_err(|message| std::io::Error::new(std::io::ErrorKind::Other, message))?;

            let backend_state = app.state::<BackendProcess>();

            let mut process_guard = backend_state.0.lock().map_err(|_| {
                std::io::Error::new(
                    std::io::ErrorKind::Other,
                    "Could not lock backend process state.",
                )
            })?;

            *process_guard = Some(backend_process);

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Tauri application");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            stop_backend(app_handle);
        }
    });
}
