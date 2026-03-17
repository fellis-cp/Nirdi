#!/usr/bin/env bash

set -e

echo "Installing Nirdi (Niri Monitor Manager)..."

# 1. Check dependencies
if ! command -v pacman >/dev/null 2>&1; then
    echo "Warning: pacman not found. Assuming you have dependencies installed manunally."
else
    # Check if packages are installed
    MISSING_PKGS=""
    if ! pacman -Qs niri >/dev/null 2>&1; then MISSING_PKGS="$MISSING_PKGS niri"; fi
    if ! pacman -Qs gtk4 >/dev/null 2>&1; then MISSING_PKGS="$MISSING_PKGS gtk4"; fi
    if ! pacman -Qs python-gobject >/dev/null 2>&1; then MISSING_PKGS="$MISSING_PKGS python-gobject"; fi
    if ! pacman -Qs wlr-randr >/dev/null 2>&1; then MISSING_PKGS="$MISSING_PKGS wlr-randr"; fi

    if [ -n "$MISSING_PKGS" ]; then
        echo "Missing dependencies: $MISSING_PKGS"
        read -p "Would you like to install them with pacman? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo pacman -S $MISSING_PKGS
        else
            echo "Please install them manually before running Nirdi."
        fi
    fi
fi

# 2. Determine target directories
INSTALL_DIR="$HOME/.local/share/nirdi"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

# 3. Create target directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# 4. Copy sources
echo "Copying application files to $INSTALL_DIR..."
rm -rf "$INSTALL_DIR/*" 2>/dev/null || true
cp -r src/* "$INSTALL_DIR/"

# 5. Create launcher script
echo "Creating launcher at $BIN_DIR/nirdi..."
cat > "$BIN_DIR/nirdi" << EOF
#!/usr/bin/env bash
export PYTHONPATH="$INSTALL_DIR:\$PYTHONPATH"
exec python3 -m nirdi "\$@"
EOF

chmod +x "$BIN_DIR/nirdi"

# 6. Install desktop file
echo "Installing desktop entry to $DESKTOP_DIR/niri-monitor-manager.desktop..."
cp niri-monitor-manager.desktop "$DESKTOP_DIR/niri-monitor-manager.desktop"

# Fix the Exec path in the desktop file (incase they launch via desktop entry instead of terminal)
sed -i "s|Exec=python3 .*/main.py|Exec=$BIN_DIR/nirdi|" "$DESKTOP_DIR/niri-monitor-manager.desktop"
sed -i "s|Exec=.*|Exec=$BIN_DIR/nirdi|" "$DESKTOP_DIR/niri-monitor-manager.desktop"

echo "Installation complete!"
echo ""
echo "You can now launch it by typing 'nirdi' in your terminal,"
echo "or looking for 'Monitor Manager' in your application launcher."
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "Note: Make sure ~/.local/bin is in your system PATH!"
fi
