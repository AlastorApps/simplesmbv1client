import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from impacket.smbconnection import SMBConnection
from impacket.smb import SessionError
import threading
import os
import logging
import time
from queue import Queue, Empty

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SMBClient')

# --- Classe client SMB ottimizzata ---
class SMBv1Client:
    def __init__(self):
        self.conn = None
        self.is_connected = False
        self.current_share = None
        self.timeout = 30

    def connect(self, server_name, server_ip, username='', password='', domain='', port=139):
        """Connette al server SMB con timeout"""
        try:
            logger.info(f"Connessione a {server_ip}, user={'<anonimo>' if not username else username}, port={port}")
            self.conn = SMBConnection(remoteName=server_name, remoteHost=server_ip, sess_port=port)
            self.conn.setTimeout(self.timeout)
            self.conn.login(username, password, domain, lmhash='', nthash='', ntlmFallback=True)
            self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"Errore connessione: {e}")
            return False

    def list_shares(self):
        """Lista tutte le share disponibili"""
        if not self.is_connected:
            return []
        
        shares = []
        try:
            share_list = self.conn.listShares()
            for share in share_list:
                share_name = share['shi1_netname'][:-1]  # Rimuovi il null terminator
                if share_name and not share_name.endswith('$'):  # Escludi share amministrative
                    shares.append(share_name)
            return shares
        except Exception as e:
            logger.error(f"Errore list_shares: {e}")
            return self.try_common_shares()

    def try_common_shares(self):
        """Prova a connettersi a share comuni"""
        common_shares = ['shared', 'Public', 'Files', 'Data', 'Share', 'Documents', 'Temp', 'IPC$']
        available_shares = []
        
        for share in common_shares:
            try:
                tid = self.conn.connectTree(share)
                self.conn.disconnectTree(tid)
                available_shares.append(share)
                logger.info(f"Share trovata: {share}")
            except:
                continue
        
        return available_shares

    def select_share(self, share_name):
        """Seleziona una share specifica"""
        try:
            tid = self.conn.connectTree(share_name)
            self.conn.disconnectTree(tid)
            self.current_share = share_name
            logger.info(f"Share selezionata: {share_name}")
            return True
        except Exception as e:
            logger.error(f"Share {share_name} non accessibile: {e}")
            return False

    def list_files_paginated(self, path="\\", limit=1000, file_filter=None):
        """Lista file con limite per performance e filtri"""
        if not self.is_connected or not self.current_share:
            return []

        files = []
        try:
            tid = self.conn.connectTree(self.current_share)
            
            if path == "\\" or path == "":
                search_path = "*"
            else:
                path = path.replace('/', '\\')
                if path.endswith('\\'):
                    search_path = path + "*"
                else:
                    search_path = path + "\\*"
            
            logger.debug(f"Search path: '{search_path}'")
            
            file_list = self.conn.listPath(self.current_share, search_path)
            logger.info(f"Trovati {len(file_list)} elementi totali")
            
            count = 0
            for f in file_list:
                if count >= limit:
                    break
                    
                try:
                    name = f.get_longname()
                    if name in ['.', '..']:
                        continue
                    
                    is_directory = f.is_directory()
                    
                    # Applica filtro se specificato
                    if file_filter:
                        if file_filter == "folders" and not is_directory:
                            continue
                        elif file_filter == "files" and is_directory:
                            continue
                    
                    files.append({
                        'filename': name,
                        'is_directory': is_directory,
                        'size': f.get_filesize()
                    })
                    
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Errore processando file entry: {e}")
                    continue

            self.conn.disconnectTree(tid)
            return files
            
        except SessionError as e:
            logger.error(f"Errore SMB list_files: {e}")
            return []
        except Exception as e:
            logger.error(f"Errore generico list_files: {e}")
            return []

    def download_file(self, remote_path, local_path, progress_callback=None):
        """Scarica un file dalla share corrente con progresso"""
        if not self.is_connected or not self.current_share:
            return False
        try:
            remote_path = remote_path.replace('/', '\\')
            if not remote_path.startswith('\\'):
                remote_path = '\\' + remote_path
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            tid = self.conn.connectTree(self.current_share)
            fid = self.conn.openFile(tid, remote_path)
            
            # Ottieni dimensione file per progresso
            file_size = self.conn.getFileSize(tid, fid)
            downloaded = 0
            
            with open(local_path, 'wb') as f:
                offset = 0
                while True:
                    try:
                        data = self.conn.readFile(tid, fid, offset, 8192)
                        if not data:
                            break
                        f.write(data)
                        offset += len(data)
                        downloaded += len(data)
                        
                        # Callback progresso
                        if progress_callback and file_size > 0:
                            progress = (downloaded / file_size) * 100
                            progress_callback(progress)
                            
                    except Exception as e:
                        logger.error(f"Errore durante la lettura: {e}")
                        break

            self.conn.closeFile(tid, fid)
            self.conn.disconnectTree(tid)
            logger.info(f"File scaricato: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"Errore download_file: {e}")
            return False

    def upload_file(self, local_path, remote_path, progress_callback=None):
        """Carica un file sulla share corrente con progresso"""
        if not self.is_connected or not self.current_share:
            return False
        try:
            remote_path = remote_path.replace('/', '\\')
            if not remote_path.startswith('\\'):
                remote_path = '\\' + remote_path

            # Leggi il file locale
            file_size = os.path.getsize(local_path)
            uploaded = 0
            
            with open(local_path, 'rb') as f:
                file_data = f.read()

            tid = self.conn.connectTree(self.current_share)
            
            # Crea il file remoto
            fid = self.conn.createFile(tid, remote_path)
            
            # Scrivi i dati
            self.conn.writeFile(tid, fid, file_data)
            
            # Callback progresso
            if progress_callback:
                progress_callback(100)
            
            # Chiudi il file
            self.conn.closeFile(tid, fid)
            self.conn.disconnectTree(tid)
            
            logger.info(f"File caricato: {local_path} -> {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Errore upload_file: {e}")
            return False

    def create_directory(self, path):
        """Crea una nuova directory"""
        if not self.is_connected or not self.current_share:
            return False
        try:
            path = path.replace('/', '\\')
            if not path.startswith('\\'):
                path = '\\' + path

            tid = self.conn.connectTree(self.current_share)
            self.conn.createDirectory(self.current_share, path)
            self.conn.disconnectTree(tid)
            
            logger.info(f"Directory creata: {path}")
            return True
        except Exception as e:
            logger.error(f"Errore create_directory: {e}")
            return False

    def disconnect(self):
        """Disconnette in modo sicuro"""
        if self.conn:
            try:
                self.conn.logoff()
                logger.info("Disconnessione effettuata")
            except Exception as e:
                logger.error(f"Errore durante la disconnessione: {e}")
            finally:
                self.conn = None
                self.is_connected = False
                self.current_share = None
        else:
            self.is_connected = False
            self.current_share = None

# --- GUI Ottimizzata ---
class SMBClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple SMBv1 Client")
        self.root.geometry("1200x800")

        self.smb_client = SMBv1Client()
        self.current_path = "\\"
        self.connected = False
        self.file_limit = 1000  # Limite file visualizzati
        self.current_files = []  # Cache file correnti
        
        # Variabili per filtri
        self.show_files_var = tk.BooleanVar(value=True)
        self.show_folders_var = tk.BooleanVar(value=True)
        self.search_var = tk.StringVar()
        self.file_type_filter = tk.StringVar(value="all")  # all, folders, files
        
        self.setup_ui()

    def setup_ui(self):
        # Frame principale
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Connessione
        conn_frame = ttk.LabelFrame(main_frame, text="Connessione SMB v1", padding=10)
        conn_frame.pack(fill="x", pady=(0, 10))

        # Riga 1 - Server
        ttk.Label(conn_frame, text="Server IP:*").grid(row=0, column=0, sticky="w", padx=5)
        self.server_ip = ttk.Entry(conn_frame, width=20)
        self.server_ip.grid(row=0, column=1, padx=5)
        self.server_ip.insert(0, "1.1.1.1")

        ttk.Label(conn_frame, text="Server Name:*").grid(row=0, column=2, sticky="w", padx=(20,5))
        self.server_name = ttk.Entry(conn_frame, width=20)
        self.server_name.grid(row=0, column=3, padx=5)
        self.server_name.insert(0, "SERVER")

        # Riga 2 - Autenticazione
        self.anonymous_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(conn_frame, text="Connessione anonima", 
                       variable=self.anonymous_var,
                       command=self.toggle_auth_fields).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

        ttk.Label(conn_frame, text="Username:").grid(row=1, column=2, sticky="w", padx=(20,5))
        self.username = ttk.Entry(conn_frame, width=20)
        self.username.grid(row=1, column=3, padx=5)

        ttk.Label(conn_frame, text="Password:").grid(row=2, column=2, sticky="w", padx=(20,5))
        self.password = ttk.Entry(conn_frame, width=20, show="*")
        self.password.grid(row=2, column=3, padx=5)

        self.connect_btn = ttk.Button(conn_frame, text="🔌 Connetti", command=self.connect_server)
        self.connect_btn.grid(row=0, column=4, rowspan=3, padx=20, sticky="ns")

        # Frame selezione share
        share_frame = ttk.LabelFrame(main_frame, text="Selezione Share", padding=10)
        share_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(share_frame, text="Share disponibili:").pack(side="left")
        self.share_combobox = ttk.Combobox(share_frame, width=30, state="readonly")
        self.share_combobox.pack(side="left", padx=10)
        
        self.select_share_btn = ttk.Button(share_frame, text="✅ Seleziona Share", 
                                         command=self.select_share, state="disabled")
        self.select_share_btn.pack(side="left", padx=5)
        
        ttk.Button(share_frame, text="🔄 Aggiorna Shares", command=self.refresh_shares).pack(side="left", padx=5)

        # Info connessione
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(info_frame, text="Share corrente:").pack(side="left")
        self.current_share_label = ttk.Label(info_frame, text="Nessuna", font=("Arial", 10, "bold"), foreground="red")
        self.current_share_label.pack(side="left", padx=5)
        
        ttk.Label(info_frame, text="Stato:").pack(side="left", padx=(20,0))
        self.connection_status_label = ttk.Label(info_frame, text="Disconnesso", font=("Arial", 10), foreground="red")
        self.connection_status_label.pack(side="left", padx=5)

        # Percorso corrente
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(path_frame, text="Percorso corrente:").pack(side="left")
        self.current_path_label = ttk.Label(path_frame, text="\\", font=("Arial", 10, "bold"), foreground="blue")
        self.current_path_label.pack(side="left", padx=5)

        # Navigazione
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Button(nav_frame, text="📂 Root", command=self.go_root).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="↑ Cartella Superiore", command=self.go_up).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="🔄 Aggiorna", command=self.refresh_files).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="📁 Nuova Cartella", command=self.create_folder).pack(side="left", padx=2)

        # Filtri
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filtri:").pack(side="left")
        
        # Filtro tipo
        ttk.Radiobutton(filter_frame, text="Tutto", variable=self.file_type_filter, 
                       value="all", command=self.apply_filters_and_refresh).pack(side="left", padx=5)
        ttk.Radiobutton(filter_frame, text="Solo Cartelle", variable=self.file_type_filter, 
                       value="folders", command=self.apply_filters_and_refresh).pack(side="left", padx=5)
        ttk.Radiobutton(filter_frame, text="Solo File", variable=self.file_type_filter, 
                       value="files", command=self.apply_filters_and_refresh).pack(side="left", padx=5)
        
        # Ricerca
        ttk.Label(filter_frame, text="Cerca:").pack(side="left", padx=(20,0))
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind('<KeyRelease>', lambda e: self.apply_filters_and_refresh())
        
        ttk.Button(filter_frame, text="Pulisci", command=self.clear_search).pack(side="left", padx=5)

        # Lista file
        files_frame = ttk.LabelFrame(main_frame, text="Contenuto", padding=10)
        files_frame.pack(fill="both", expand=True)

        # Treeview con scorrimento virtuale
        columns = ("Nome", "Dimensione", "Tipo", "Ultima Modifica")
        self.files_tree = ttk.Treeview(files_frame, columns=columns, show="headings", selectmode="browse")
        
        for col in columns:
            self.files_tree.heading(col, text=col)
        
        self.files_tree.column("Nome", width=400, anchor="w")
        self.files_tree.column("Dimensione", width=120, anchor="e")
        self.files_tree.column("Tipo", width=100, anchor="center")
        self.files_tree.column("Ultima Modifica", width=150, anchor="center")

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_tree.yview)
        h_scrollbar = ttk.Scrollbar(files_frame, orient="horizontal", command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.files_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        files_frame.grid_rowconfigure(0, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        self.files_tree.bind("<Double-1>", self.on_item_double_click)

        # Progress bar per operazioni lunghe
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.pack(fill="x", pady=(5, 0))

        # Azioni
        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(actions_frame, text="📥 Scarica File", command=self.download_file).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="📤 Carica File", command=self.upload_file).pack(side="left", padx=5)
        
        # Controlli limite file
        limit_frame = ttk.Frame(actions_frame)
        limit_frame.pack(side="left", padx=20)
        
        ttk.Label(limit_frame, text="Limite file:").pack(side="left")
        self.limit_var = tk.StringVar(value="1000")
        limit_combo = ttk.Combobox(limit_frame, textvariable=self.limit_var, 
                                  values=["500", "1000", "2000", "5000"], 
                                  width=8, state="readonly")
        limit_combo.pack(side="left", padx=5)
        limit_combo.bind('<<ComboboxSelected>>', self.on_limit_changed)
        
        self.disconnect_btn = ttk.Button(actions_frame, text="❌ Disconnetti", command=self.disconnect_server)
        self.disconnect_btn.pack(side="right", padx=5)
        self.disconnect_btn.config(state="disabled")

        # Status
        self.status_var = tk.StringVar(value="Pronto per la connessione")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief="sunken", padding=5)
        status_bar.pack(fill="x", pady=(10, 0))

        # Inizializza campi autenticazione
        self.toggle_auth_fields()

    def toggle_auth_fields(self):
        """Abilita/disabilita i campi di autenticazione"""
        if self.anonymous_var.get():
            self.username.config(state="disabled")
            self.password.config(state="disabled")
        else:
            self.username.config(state="normal")
            self.password.config(state="normal")

    def connect_server(self):
        server_ip = self.server_ip.get().strip()
        server_name = self.server_name.get().strip()
        
        if not server_ip or not server_name:
            messagebox.showerror("Errore", "Inserisci IP e nome del server")
            return

        if self.anonymous_var.get():
            username = password = domain = ''
        else:
            username = self.username.get().strip()
            password = self.password.get()
            domain = ''

        self.status_var.set("Connessione in corso...")
        self.connect_btn.config(state="disabled")
        self.progress.start()

        def thread_func():
            success = self.smb_client.connect(server_name, server_ip, username, password, domain, port=139)
            self.root.after(0, lambda: self.on_connect_result(success))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_connect_result(self, success):
        self.progress.stop()
        if success:
            self.connected = True
            self.status_var.set("Connesso - Ricerca share disponibili...")
            self.connection_status_label.config(text="Connesso", foreground="green")
            self.refresh_shares()
        else:
            self.connected = False
            self.status_var.set("Errore di connessione")
            self.connection_status_label.config(text="Errore", foreground="red")
            self.connect_btn.config(state="normal")
            messagebox.showerror("Errore", "Connessione fallita")

    def refresh_shares(self):
        """Aggiorna la lista delle share disponibili"""
        def thread_func():
            shares = self.smb_client.list_shares()
            self.root.after(0, lambda: self.on_shares_loaded(shares))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_shares_loaded(self, shares):
        """Gestisce il caricamento delle share"""
        if shares:
            self.share_combobox['values'] = shares
            self.select_share_btn.config(state="normal")
            self.status_var.set(f"Trovate {len(shares)} share - Seleziona una share")
            if len(shares) == 1:
                self.share_combobox.set(shares[0])
                messagebox.showinfo("Successo", f"Trovata 1 share: {shares[0]}")
            else:
                messagebox.showinfo("Successo", f"Trovate {len(shares)} share disponibili")
        else:
            self.share_combobox.set('')
            self.share_combobox['values'] = []
            self.select_share_btn.config(state="disabled")
            self.status_var.set("Nessuna share trovata")
            messagebox.showwarning("Attenzione", "Nessuna share trovata")
        
        self.connect_btn.config(state="normal")

    def select_share(self):
        """Seleziona la share scelta dall'utente"""
        selected_share = self.share_combobox.get()
        if not selected_share:
            messagebox.showwarning("Attenzione", "Seleziona una share dalla lista")
            return

        self.status_var.set(f"Connessione alla share {selected_share}...")
        self.select_share_btn.config(state="disabled")

        def thread_func():
            success = self.smb_client.select_share(selected_share)
            self.root.after(0, lambda: self.on_share_selected(success, selected_share))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_share_selected(self, success, share_name):
        if success:
            self.current_share_label.config(text=share_name, foreground="green")
            self.status_var.set(f"Share {share_name} selezionata - Caricamento file...")
            self.current_path = "\\"
            self.current_path_label.config(text=self.current_path)
            self.load_files()
            self.disconnect_btn.config(state="normal")
        else:
            self.status_var.set(f"Errore selezione share {share_name}")
            self.select_share_btn.config(state="normal")
            messagebox.showerror("Errore", f"Impossibile accedere alla share {share_name}")

    def load_files(self):
        """Carica i file dalla share con caricamento ottimizzato"""
        if not self.connected:
            return
            
        self.clear_treeview()
        self.status_var.set(f"Caricamento da {self.smb_client.current_share}{self.current_path}...")
        
        # Mostra indicatore di caricamento
        loading_item = self.files_tree.insert("", "end", values=("⏳ Caricamento in corso...", "", "", ""))
        
        def thread_func():
            try:
                start_time = time.time()
                file_filter = self.file_type_filter.get() if self.file_type_filter.get() != "all" else None
                files = self.smb_client.list_files_paginated(self.current_path, 
                                                           limit=int(self.limit_var.get()),
                                                           file_filter=file_filter)
                elapsed_time = time.time() - start_time
                logger.info(f"Caricamento completato in {elapsed_time:.2f}s - {len(files)} file")
                self.root.after(0, lambda: self.on_files_loaded(files, loading_item, elapsed_time))
            except Exception as e:
                logger.error(f"Errore durante il caricamento file: {e}")
                self.root.after(0, lambda: self.on_files_loaded([], loading_item, 0))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_files_loaded(self, files, loading_item, elapsed_time):
        """Mostra i file nella treeview"""
        if not self.connected:
            return
        
        # Rimuovi indicatore di caricamento
        if loading_item in self.files_tree.get_children():
            self.files_tree.delete(loading_item)
        
        self.current_files = files  # Salva in cache per filtri
        
        # Applica filtri di ricerca
        filtered_files = self.apply_search_filter(files)
        
        # Aggiungi ".." per tornare su (se non siamo alla root)
        if self.current_path != "\\":
            self.files_tree.insert("", "end", values=("..", "", "📁 Cartella", ""))

        # Separa cartelle e file
        folders = []
        file_items = []
        
        for f in filtered_files:
            filename = f['filename']
            is_dir = f['is_directory']
            size = f['size']
            
            file_type = "📁 Cartella" if is_dir else "📄 File"
            size_str = "" if is_dir else self.format_size(size)
            
            if is_dir:
                folders.append((filename, size_str, file_type, ""))
            else:
                file_items.append((filename, size_str, file_type, ""))

        # Inserisci prima le cartelle, poi i file (ordinati)
        for folder in sorted(folders, key=lambda x: x[0].lower()):
            self.files_tree.insert("", "end", values=folder)
        
        for file_item in sorted(file_items, key=lambda x: x[0].lower()):
            self.files_tree.insert("", "end", values=file_item)
        
        # Messaggio informativo se raggiunto il limite
        total_loaded = len(filtered_files)
        if total_loaded >= int(self.limit_var.get()):
            self.files_tree.insert("", "end", values=(
                f"⚠️ Visualizzati {total_loaded} elementi (limite raggiunto)", 
                "", "Info", ""))
        
        self.status_var.set(
            f"{self.smb_client.current_share}{self.current_path} - "
            f"{total_loaded} elementi - {elapsed_time:.2f}s"
        )

    def apply_search_filter(self, files):
        """Applica filtro di ricerca alla lista file"""
        search_term = self.search_var.get().lower().strip()
        if not search_term:
            return files
        
        filtered = []
        for f in files:
            if search_term in f['filename'].lower():
                filtered.append(f)
        return filtered

    def apply_filters_and_refresh(self):
        """Applica tutti i filtri e ricarica"""
        if self.connected:
            self.load_files()

    def clear_search(self):
        """Pulisce la ricerca"""
        self.search_var.set("")
        self.apply_filters_and_refresh()

    def on_limit_changed(self, event=None):
        """Gestisce il cambio del limite file"""
        if self.connected:
            self.load_files()

    def format_size(self, size):
        """Formatta la dimensione del file in modo leggibile"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def clear_treeview(self):
        """Svuota la treeview"""
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)

    def go_root(self):
        """Torna alla radice"""
        if not self.connected:
            return
        self.current_path = "\\"
        self.current_path_label.config(text=self.current_path)
        self.load_files()

    def go_up(self):
        """Torna alla cartella superiore"""
        if not self.connected or self.current_path == "\\":
            return
        
        parts = [p for p in self.current_path.split("\\") if p]
        if len(parts) > 1:
            parts.pop()
            self.current_path = "\\" + "\\".join(parts) + "\\"
        else:
            self.current_path = "\\"
        
        self.current_path_label.config(text=self.current_path)
        self.load_files()

    def refresh_files(self):
        """Aggiorna la lista"""
        if self.connected:
            self.load_files()

    def create_folder(self):
        """Crea una nuova cartella"""
        if not self.connected:
            messagebox.showwarning("Attenzione", "Non connesso al server")
            return
            
        folder_name = simpledialog.askstring("Nuova Cartella", "Nome della nuova cartella:")
        if folder_name:
            remote_path = os.path.join(self.current_path, folder_name).replace("/", "\\")
            
            def thread_func():
                success = self.smb_client.create_directory(remote_path)
                self.root.after(0, lambda: self.on_folder_created(success, folder_name))
            
            threading.Thread(target=thread_func, daemon=True).start()

    def on_folder_created(self, success, folder_name):
        if success:
            messagebox.showinfo("Successo", f"Cartella '{folder_name}' creata")
            self.load_files()
        else:
            messagebox.showerror("Errore", f"Errore nella creazione della cartella '{folder_name}'")

    def on_item_double_click(self, event):
        """Gestisce il doppio click"""
        if not self.connected:
            return
            
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = self.files_tree.item(selection[0])
        name = item['values'][0]
        
        # Ignora messaggi informativi
        if name.startswith("⚠️") or name.startswith("⏳"):
            return

        if "Cartella" in item['values'][2]:
            if name == "..":
                self.go_up()
            else:
                # Entra nella cartella
                new_path = os.path.join(self.current_path, name).replace("/", "\\")
                if not new_path.endswith("\\"):
                    new_path += "\\"
                self.current_path = new_path
                self.current_path_label.config(text=self.current_path)
                self.load_files()

    def download_file(self):
        """Scarica il file selezionato con progresso"""
        if not self.connected:
            messagebox.showwarning("Attenzione", "Non connesso al server")
            return
            
        selection = self.files_tree.selection()
        if not selection:
            messagebox.showwarning("Attenzione", "Seleziona un file da scaricare")
            return
        
        item = self.files_tree.item(selection[0])
        filename = item['values'][0]
        
        # Ignora elementi speciali
        if filename.startswith("⚠️") or filename.startswith("⏳"):
            return
            
        if "Cartella" in item['values'][2]:
            messagebox.showwarning("Attenzione", "Seleziona un file, non una cartella")
            return

        local_path = filedialog.asksaveasfilename(
            title="Salva file come",
            initialfile=filename,
            initialdir=os.path.expanduser("~/Downloads")
        )
        
        if not local_path:
            return

        self.status_var.set(f"Download {filename}...")
        self.progress['value'] = 0
        
        def progress_callback(progress):
            self.root.after(0, lambda: self.progress.config(value=progress))

        def thread_func():
            try:
                remote_path = os.path.join(self.current_path, filename).replace("/", "\\")
                success = self.smb_client.download_file(remote_path, local_path, progress_callback)
                self.root.after(0, lambda: self.on_download_result(success, filename))
            except Exception as e:
                logger.error(f"Errore durante il download: {e}")
                self.root.after(0, lambda: self.on_download_result(False, filename))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_download_result(self, success, filename):
        self.progress['value'] = 0
        if success:
            messagebox.showinfo("Successo", f"File scaricato: {filename}")
            self.status_var.set("Download completato")
        else:
            messagebox.showerror("Errore", f"Errore download: {filename}")
            self.status_var.set("Errore download")

    def upload_file(self):
        """Carica un file sul server con progresso"""
        if not self.connected:
            messagebox.showwarning("Attenzione", "Non connesso al server")
            return
            
        local_path = filedialog.askopenfilename(
            title="Seleziona file da caricare",
            initialdir=os.path.expanduser("~")
        )
        
        if not local_path:
            return

        filename = os.path.basename(local_path)
        remote_path = os.path.join(self.current_path, filename).replace("/", "\\")

        self.status_var.set(f"Upload {filename}...")
        self.progress['value'] = 0
        
        def progress_callback(progress):
            self.root.after(0, lambda: self.progress.config(value=progress))

        def thread_func():
            try:
                success = self.smb_client.upload_file(local_path, remote_path, progress_callback)
                self.root.after(0, lambda: self.on_upload_result(success, filename))
            except Exception as e:
                logger.error(f"Errore durante l'upload: {e}")
                self.root.after(0, lambda: self.on_upload_result(False, filename))
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_upload_result(self, success, filename):
        self.progress['value'] = 0
        if success:
            messagebox.showinfo("Successo", f"File caricato: {filename}")
            self.status_var.set("Upload completato")
            self.load_files()  # Ricarica la lista
        else:
            messagebox.showerror("Errore", f"Errore upload: {filename}")
            self.status_var.set("Errore upload")

    def disconnect_server(self):
        """Disconnette in modo sicuro"""
        if not self.connected:
            return
            
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="disabled")
        self.select_share_btn.config(state="disabled")
        self.status_var.set("Disconnessione in corso...")
        
        def thread_func():
            try:
                self.smb_client.disconnect()
                self.root.after(0, self.on_disconnect_complete)
            except Exception as e:
                logger.error(f"Errore durante la disconnessione: {e}")
                self.root.after(0, self.on_disconnect_complete)
        
        threading.Thread(target=thread_func, daemon=True).start()

    def on_disconnect_complete(self):
        """Completamento della disconnessione"""
        self.clear_treeview()
        self.current_path = "\\"
        self.current_path_label.config(text="\\")
        self.current_share_label.config(text="Nessuna", foreground="red")
        self.connection_status_label.config(text="Disconnesso", foreground="red")
        self.connected = False
        self.current_files = []
        
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.select_share_btn.config(state="disabled")
        self.share_combobox.set('')
        self.share_combobox['values'] = []
        self.status_var.set("Disconnesso")
        
        messagebox.showinfo("Info", "Disconnesso dal server")

    def on_closing(self):
        """Gestisce la chiusura della finestra"""
        if self.connected:
            self.smb_client.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SMBClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
