use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
    time::Duration,
};

use tauri::{Manager, RunEvent};

struct BackendProcess(Mutex<Option<Child>>);

#[allow(unused_variables)]
fn start_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    let (python_path, python_home, site_packages, backend_script, working_dir): (
        PathBuf,
        PathBuf,
        PathBuf,
        PathBuf,
        PathBuf,
    );

    #[cfg(debug_assertions)]
    {
        // CARGO_MANIFEST_DIR:
        // <project>/papertranslate-ui/src-tauri
        let tauri_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));

        let project_root = tauri_dir
            .join("../..")
            .canonicalize()
            .map_err(|error| format!("Could not resolve project root: {error}"))?;

        let runtime_dir = project_root.join("desktop-runtime");

        python_home = runtime_dir
            .join("python")
            .join("cpython-3.10.20-linux-x86_64-gnu");

        python_path = python_home.join("bin").join("python3.10");

        site_packages = runtime_dir
            .join("venv")
            .join("lib")
            .join("python3.10")
            .join("site-packages");

        backend_script = project_root.join("backend").join("run_backend.py");

        working_dir = project_root.join("backend");
    }

    #[cfg(not(debug_assertions))]
    {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| format!("Could not resolve Tauri resource directory: {error}"))?;

        let runtime_dir = resource_dir.join("runtime");

        python_home = runtime_dir
            .join("python")
            .join("cpython-3.10.20-linux-x86_64-gnu");

        python_path = python_home.join("bin").join("python3.10");

        site_packages = runtime_dir
            .join("venv")
            .join("lib")
            .join("python3.10")
            .join("site-packages");

        backend_script = resource_dir.join("backend-app").join("run_backend.py");

        working_dir = resource_dir.join("backend-app");
    }

    if !python_path.exists() {
        return Err(format!(
            "Bundled Python executable was not found: {}",
            python_path.display()
        ));
    }

    if !python_home.exists() {
        return Err(format!(
            "Bundled Python home was not found: {}",
            python_home.display()
        ));
    }

    if !site_packages.exists() {
        return Err(format!(
            "Bundled Python site-packages was not found: {}",
            site_packages.display()
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
    println!("Python home: {}", python_home.display());
    println!("Python site-packages: {}", site_packages.display());
    println!("Backend script: {}", backend_script.display());
    println!("App data directory: {}", app_data_dir.display());

    Command::new(&python_path)
        .arg(&backend_script)
        .current_dir(&working_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONHOME", &python_home)
        .env("PYTHONPATH", &site_packages)
        .env("PAPERTRANSLATE_DATA_DIR", &app_data_dir)
        .spawn()
        .map_err(|error| format!("Failed to start bundled Python backend: {error}"))
}

fn shutdown_managed_models() -> Result<(), String> {
    let address = SocketAddr::from(([127, 0, 0, 1], 8002));

    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(2))
        .map_err(|error| format!("Could not connect to backend for cleanup: {error}"))?;

    stream
        .set_read_timeout(Some(Duration::from_secs(50)))
        .map_err(|error| format!("Could not set cleanup read timeout: {error}"))?;

    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| format!("Could not set cleanup write timeout: {error}"))?;

    let request = concat!(
        "POST /pipeline/model-manager/shutdown HTTP/1.1\r\n",
        "Host: 127.0.0.1:8002\r\n",
        "Connection: close\r\n",
        "Content-Length: 0\r\n",
        "\r\n"
    );

    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("Could not send model cleanup request: {error}"))?;

    let mut response = String::new();

    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("Could not read model cleanup response: {error}"))?;

    if response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200") {
        println!("Managed model cleanup completed.");
        return Ok(());
    }

    Err(format!(
        "Backend cleanup returned an unsuccessful response: {}",
        response.lines().next().unwrap_or("empty response")
    ))
}

fn stop_backend(app_handle: &tauri::AppHandle) {
    // Ask the still-running backend to stop its owned model
    // processes before terminating the backend itself.
    if let Err(error) = shutdown_managed_models() {
        eprintln!("{error}");
    }

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
