use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[tauri::command]
fn open_cv_preview(app: tauri::AppHandle, html: String) -> Result<(), String> {
    // Write HTML to temp file — data URIs have size limits in some WebViews
    let tmp = std::env::temp_dir().join("jh-cv-preview.html");
    std::fs::write(&tmp, html.as_bytes()).map_err(|e| e.to_string())?;
    let url_str = format!(
        "file://{}",
        tmp.to_str().unwrap_or_default().replace('\\', "/")
    );
    let url = url::Url::parse(&url_str).map_err(|e| e.to_string())?;

    // Close existing preview window if already open
    if let Some(existing) = app.get_webview_window("cv-preview") {
        let _ = existing.close();
    }

    tauri::WebviewWindowBuilder::new(&app, "cv-preview", tauri::WebviewUrl::External(url))
        .title("CV Preview — press Ctrl+P to save as PDF")
        .width(900)
        .height(1200)
        .build()
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;

            // In dev mode, sidecar may not exist — skip gracefully
            let sidecar_result = app
                .shell()
                .sidecar("job-hunter-backend")
                .map(|cmd| cmd.env("JH_DATA_DIR", data_dir.to_str().unwrap_or_default()))
                .and_then(|cmd| cmd.spawn());

            match sidecar_result {
                Ok((_rx, child)) => {
                    app.manage(child);
                }
                Err(e) => {
                    eprintln!("Sidecar not found (dev mode?): {e}");
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![open_cv_preview])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
