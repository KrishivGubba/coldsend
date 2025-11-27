// ColdSend Background Service Worker

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('ColdSend extension installed');
    // Initialize default settings
    chrome.storage.local.set({
      enabled: true,
      settings: {
        autoHighlight: true
      }
    });
  }
});

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'getProfileData':
      // Handle profile data requests
      sendResponse({ success: true, data: message.data });
      break;
    
    case 'checkLinkedInPage':
      // Check if current tab is a LinkedIn page
      if (sender.tab) {
        const isLinkedIn = sender.tab.url?.includes('linkedin.com');
        sendResponse({ isLinkedIn });
      }
      break;
    
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
  
  // Return true to indicate async response
  return true;
});

// Listen for tab updates to detect LinkedIn navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url?.includes('linkedin.com')) {
    // Notify content script that page is ready
    chrome.tabs.sendMessage(tabId, { action: 'pageReady' }).catch(() => {
      // Content script might not be ready yet, ignore error
    });
  }
});

