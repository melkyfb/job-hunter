use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Key, Nonce,
};
use rand::RngCore;
use std::net::TcpListener;
use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_log::{Target, TargetKind};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

const KEYRING_SERVICE: &str = "io.github.melkyfb.jobhunter";
const KEYRING_USER: &str = "config-key";
const CONFIG_FILE: &str = "config.enc";

// Estrutura para armazenar o estado do backend na memória do Tauri
struct BackendState {
    port: u16,
    child_process: Mutex<Option<CommandChild>>,
}

// Função auxiliar para encontrar uma porta TCP livre no sistema
fn get_available_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port()
}

// Comando para o frontend requisitar a porta
#[tauri::command]
fn get_backend_port(state: tauri::State<BackendState>) -> u16 {
    state.port
}

fn get_or_create_key() -> Result<[u8; 32], String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER).map_err(|e| e.to_string())?;

    match entry.get_password() {
        Ok(hex) => {
            let bytes = hex::decode(&hex).map_err(|e| e.to_string())?;
            if bytes.len() != 32 {
                return Err("Invalid key length in keychain".into());
            }
            let mut key = [0u8; 32];
            key.copy_from_slice(&bytes);
            Ok(key)
        }
        Err(_) => {
            let mut key = [0u8; 32];
            rand::thread_rng().fill_bytes(&mut key);
            let hex = hex::encode(key);
            entry.set_password(&hex).map_err(|e| e.to_string())?;
            Ok(key)
        }
    }
}

#[tauri::command]
fn save_secure_config(app: tauri::AppHandle, json: String) -> Result<(), String> {
    let key_bytes = get_or_create_key()?;
    let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
    let cipher = Aes256Gcm::new(key);

    let mut nonce_bytes = [0u8; 12];
    rand::thread_rng().fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, json.as_bytes())
        .map_err(|e| e.to_string())?;

    // Format: 12 bytes nonce || ciphertext
    let mut data = Vec::with_capacity(12 + ciphertext.len());
    data.extend_from_slice(&nonce_bytes);
    data.extend_from_slice(&ciphertext);

    let path = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join(CONFIG_FILE);
    std::fs::write(path, &data).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn load_secure_config(app: tauri::AppHandle) -> Result<String, String> {
    let path = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join(CONFIG_FILE);

    if !path.exists() {
        return Ok(String::new());
    }

    let data = std::fs::read(&path).map_err(|e| e.to_string())?;
    if data.len() < 13 {
        return Err("Config file too short".into());
    }

    let key_bytes = get_or_create_key()?;
    let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
    let cipher = Aes256Gcm::new(key);

    let nonce = Nonce::from_slice(&data[..12]);
    let plaintext = cipher
        .decrypt(nonce, &data[12..])
        .map_err(|_| "Decryption failed — key mismatch or corrupted file".to_string())?;

    String::from_utf8(plaintext).map_err(|e| e.to_string())
}

#[tauri::command]
fn open_cv_preview(app: tauri::AppHandle, html: String) -> Result<(), String> {
    let tmp = std::env::temp_dir().join("jh-cv-preview.html");
    std::fs::write(&tmp, html.as_bytes()).map_err(|e| e.to_string())?;
    let path_str = tmp.to_str().unwrap_or_default().replace('\\', "/");
    let url_str = format!("file:///{}", path_str.trim_start_matches('/'));
    let url = url_str.parse::<url::Url>().map_err(|e| e.to_string())?;

    if let Some(existing) = app.get_webview_window("cv-preview") {
        let _ = existing.close();
    }

    tauri::WebviewWindowBuilder::new(&app, "cv-preview", tauri::WebviewUrl::External(url))
        .title("CV Preview — press Ctrl+P to save as PDF")
        .inner_size(900.0, 1200.0)
        .build()
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn run() {
    // 1. Gera a porta dinâmica antes de iniciar o Tauri
    let port = get_available_port();

    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::new()
                .targets([
                    Target::new(TargetKind::LogDir { file_name: Some("app".into()) }),
                    Target::new(TargetKind::Stderr),
                ])
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .setup(move |app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;

            // 2. Passa a porta selecionada via argumento (--port XXXX)
            let sidecar_result = app
                .shell()
                .sidecar("job-hunter-backend")
                .map(|cmd| cmd.env("JH_DATA_DIR", data_dir.to_str().unwrap_or_default()))
                .map(|cmd| cmd.args(["--port", &port.to_string()]))
                .and_then(|cmd| cmd.spawn());

            let child_process = match sidecar_result {
                Ok((_rx, child)) => {
                    Some(child)
                }
                Err(e) => {
                    eprintln!("Sidecar not found (dev mode?): {e}");
                    None
                }
            };

            // 3. Salva a porta e o processo no estado gerenciado
            app.manage(BackendState {
                port,
                child_process: Mutex::new(child_process),
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_cv_preview,
            save_secure_config,
            load_secure_config,
            get_backend_port, // Registra o comando
        ])
        .on_window_event(|window, event| match event {
            tauri::WindowEvent::Destroyed => {
                // Ponto de atenção: Garante que só matará o backend se a janela "main" for fechada
                // Isso evita que fechar a janela do "cv-preview" encerre o servidor.
                if window.label() == "main" {
                    let state = window.state::<BackendState>();
                    let mut child_guard = state.child_process.lock().unwrap();
                    if let Some(child) = child_guard.take() {
                        println!("Encerrando o servidor Python de forma segura...");
                        let _ = child.kill();
                    }
                }
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}