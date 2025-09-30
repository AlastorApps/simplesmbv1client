# Simple SMBv1 Client

A lightweight graphical SMBv1 client developed in Python for connecting to legacy Samba servers and embedded systems that require the SMB version 1 protocol.

---

## Windows Compatibility

### Important Note for Windows Users
Due to Microsoft security patch **KB5065426**, SMBv1 client functionality is disabled by default in Windows 10/11. However, this application can still function with proper configuration.

### Enabling SMBv1 on Windows
To use this application on Windows, you must enable the SMBv1 client feature.

**Via PowerShell (Admin):**
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol-Client
```

**Via Control Panel:**
1. Open *Turn Windows features on or off*
2. Check *SMB 1.0/CIFS File Sharing Support*
3. Check *SMB 1.0/CIFS Client*
4. Restart your computer

---

## Supported Platforms

- **Linux (Ubuntu, Debian, CentOS, etc.)** – Works out of the box  
- **macOS** – Works out of the box  
- **Windows** – Requires SMBv1 client feature enabled  

---

## Features

- Simple graphical interface with Tkinter  
- Remote file browsing with folder navigation  
- File download/upload functionality  
- Basic search and filtering capabilities  
- Support for large directories with configurable limits  
- Authentication support (anonymous and credentials)  
- Optimized for legacy Samba servers and embedded systems  

---

## Installation

### Prerequisites

**Windows:**
- Python 3.6 or newer  
- SMBv1 Client feature enabled (see above)  

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install python3 python3-pip tkinter
```

### Install the Application
```bash
git clone https://github.com/AlastorApps/simplesmbv1client.git
cd simplesmbv1client
pip install impacket
```

---

## Running the Application
```bash
python3 ssmbv1.py
```

---

## Usage

### Basic Connection
1. Enter server IP address (e.g., `10.0.4.11`)  
2. Enter server NetBIOS name (e.g., `SERVER`)  
3. Select authentication method (anonymous or credentials)  
4. Click *Connect*  

### File Operations
- Double-click folders to navigate  
- Use *Root* and *Up* buttons for navigation  
- Select files and use *Download*/*Upload* buttons  
- Create new folders with the *New Folder* button  

### Configuration Options
- Adjust file display limits for better performance  
- Use search filter to find specific files  
- Toggle between showing files and folders  

---

## Project Structure
```
simplesmbv1client/
├── ssmbv1.py             # Main application file
├── LICENSE               # MIT License
└── README.md             # This file
```

---

## Troubleshooting

### Connection Issues
- Verify SMBv1 is enabled on both client and server  
- Check firewall settings on port 139  
- Confirm the server supports SMBv1 protocol  
- Ensure correct server name and IP address  

### Performance Issues
- Reduce the file display limit for large directories  
- Use search filters to narrow down results  
- Check network connectivity and speed  

### Windows-Specific Issues
If SMBv1 cannot be enabled due to organizational policies, consider using:
- A Linux virtual machine  
- Windows Subsystem for Linux (WSL)  
- A dedicated Linux machine for SMBv1 connections  

---

## Security Considerations

### SMBv1 Security Notes
SMBv1 is considered insecure due to:
- Vulnerability to attacks like EternalBlue  
- Lack of modern encryption standards  
- Weak authentication mechanisms  

### Recommended Practices
- Use only in isolated, trusted networks  
- Do not expose SMBv1 servers to the internet  
- Consider upgrading legacy systems to support SMBv2/3  
- Use network segmentation for SMBv1 devices  

---

## Development

The application is built with:
- Python 3.6+  
- Tkinter for the graphical interface  
- Impacket library for SMB protocol handling  
- Threading for responsive UI during operations  

### Code Structure
- **SMBv1Client**: Handles SMB protocol operations  
- **SMBClientGUI**: Manages the user interface  
- **Threading**: Ensures non-blocking file operations  

---

## Contributing
Contributions are welcome. Possible areas of improvement:
- Performance optimizations for large directories  
- Additional file operations  
- Improved error handling  
- Enhanced user interface features  

---

## License
This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## References
- Microsoft SMBv1 Documentation  
- [Impacket Library](https://github.com/fortra/impacket)  
- SMB Protocol Specifications  
