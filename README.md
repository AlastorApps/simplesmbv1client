# SMBv1 Client - Legacy File Sharing Client

A graphical SMBv1 client developed in Python for connecting to legacy Samba servers and embedded systems that only support SMB version 1.

---

## IMPORTANT: Windows Compatibility Notice

### SMBv1 Disabled on Windows

Due to the security patch **KB5065426** released by Microsoft, SMBv1 has been completely disabled on Windows 10/11 and can no longer be reactivated.

This application **DOES NOT WORK on Windows** as of **October 2023**.

---

## Supported Platforms

- **Linux** (Ubuntu, Debian, CentOS, etc.) – *Fully Supported*
- **macOS** (all recent versions) – *Fully Supported*
- **Windows** – *Not Supported* (KB5065426)

---

## Features

- Intuitive graphical interface with **tkinter**
- Remote file browsing with folder navigation
- File download/upload with progress tracking
- Real-time search and filtering
- Performance optimization for large directories
- Authentication support (anonymous and credentials)
- Optimized for **Samba 1.9.15** and legacy systems

---

## Use Cases

- Embedded systems with SMBv1 (older routers, NAS devices)
- Industrial machinery with legacy software
- IoT devices using only SMBv1
- Laboratory equipment with older instrumentation
- Isolated networks with legacy protocols

---

## Installation

### Prerequisites

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk
```

**CentOS/RHEL:**

```bash
sudo yum install python3 python3-pip tkinter
```

### Dependencies

```bash
pip install impacket
```

---

## Running the Application

```bash
git clone https://github.com/yourrepo/smbv1-client.git
cd ssmbv1
python3 ssmbv1.py
```

---

## Configuration

### Connection Parameters

- **Server IP**: SMB server address  
- **Server Name**: NetBIOS server name (e.g., `SERVER`)  
- **Port**: `139` (default for SMBv1)  
- **Authentication**: Anonymous or with credentials  

### File Limitations

- **Display limit**: Configurable (`500–5000 files`)  
- **Filters**: By type (files/folders) and text search  

---

## Project Structure

```
smbv1-client/
├── ssmbv1.py          # Main application
├── requirements.txt       # Python dependencies
├── LICENSE                # MIT License
└── README.md              # This file
```

---

## Troubleshooting

### "Connection Failed" Error

- Verify the server supports SMBv1  
- Check firewall and network connectivity  
- Confirm port **139** is open  

### Slow Performance

- Reduce file limit in settings  
- Use filters for large directories  
- Check network speed  

### Linux-Specific Issues

```bash
# If tkinter is not installed
sudo apt install python3-tk

# Network connection permissions
sudo setcap CAP_NET_RAW+ep /usr/bin/python3.8
```

---

## Development

### Development Dependencies

```bash
pip install -r requirements.txt
```

### Code Structure

- **SMBv1Client**: Core class for SMB operations  
- **SMBClientGUI**: Tkinter graphical interface  
- **Threading**: Non-blocking operations handling  

### Extending the Application

The modular structure allows easy addition of:

- New file operations (copy, move, delete)  
- Support for other protocols  
- Interface themes  
- Automated scripting  

---

## Security

### SMBv1 Warnings

SMBv1 is an obsolete and insecure protocol that:

- Vulnerable to **EternalBlue attacks**  
- Lacks modern encryption  
- Has weak authentication  

Use only in isolated and trusted networks.

### Best Practices

- Use only in private networks  
- Do not expose to the internet  
- Isolate SMBv1 servers  
- Consider upgrading to **SMBv2/3**  

---

## Contributing

Contributions are welcome! Areas for improvement:

- Performance enhancements  
- New features  
- Documentation  
- Testing and bug fixes  

---

## License

Distributed under the **MIT License**. See `LICENSE` for details.

---

## References

- [Microsoft KB5065426](https://support.microsoft.com/help/5065426)  
- [Impacket Library](https://github.com/fortra/impacket)  
- [SMB Protocol Specification](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-smb/)  
