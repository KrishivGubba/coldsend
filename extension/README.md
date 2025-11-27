# ColdSend Chrome Extension

A Chrome extension that activates on LinkedIn pages to help with outreach.

## Features

- 🔵 Activates automatically on LinkedIn pages
- 👤 Detects and extracts profile information
- 📋 Capture profiles for outreach
- 💾 Stores captured profiles locally
- 🎨 Clean, modern dark UI

## Installation

### Development Mode

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `extension` folder from this project

### Generate Icons (Required)

Before loading the extension, you need to convert the SVG icons to PNG:

```bash
# Using ImageMagick (if installed)
cd extension/icons
for size in 16 32 48 128; do
  convert icon${size}.svg icon${size}.png
done

# Or use an online SVG to PNG converter
# Upload each SVG and download the PNG at the same size
```

Alternatively, create simple PNG icons with any image editor.

## File Structure

```
extension/
├── manifest.json      # Extension configuration
├── background.js      # Service worker for background tasks
├── content.js         # Content script injected into LinkedIn
├── styles.css         # Styles for content script elements
├── popup.html         # Extension popup UI
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── icons/             # Extension icons
│   ├── icon16.svg
│   ├── icon32.svg
│   ├── icon48.svg
│   └── icon128.svg
└── README.md          # This file
```

## Usage

1. Install the extension in Chrome
2. Navigate to any LinkedIn page
3. Click the ColdSend icon in the toolbar to see status
4. On profile pages, use the "ColdSend" button to capture profiles

## Development

The extension uses Manifest V3 with:
- Service worker for background tasks
- Content scripts for LinkedIn page interaction
- Chrome Storage API for data persistence
- Message passing between popup, background, and content scripts

## LinkedIn Page Detection

The content script detects these LinkedIn page types:
- Profile pages (`/in/...`)
- Feed page (`/feed`)
- Messaging (`/messaging`)
- Search results (`/search`)

