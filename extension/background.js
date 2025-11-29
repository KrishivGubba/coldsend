// ColdSend Background Service Worker

const API_URL = "http://localhost:3000";

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('ColdSend extension installed');
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
  
  if (message.action === 'generateEmail') {
    // Make API call to generate email
    const profileData = message.data;
    const preferences = message.preferences || {};
    
    fetch(`${API_URL}/generate-email`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        name: profileData.name,
        headline: profileData.headline,
        about: profileData.about,
        experiences: profileData.experiences,
        includeResume: preferences.includeResume || false,
        includeCoffeeChat: preferences.includeCoffeeChat || false,
        customInstructions: preferences.customInstructions || ''
      })
    })
    .then(response => response.json())
    .then(data => {
      console.log("Email generated:", data);
      sendResponse({ success: true, email: data.email, subject: data.subject });
    })
    .catch(err => {
      console.error("Error generating email:", err);
      sendResponse({ success: false, error: err.message });
    });
    
    return true; // Keep channel open for async response
  }
  
  if (message.action === 'getProfileData') {
    sendResponse({ success: true, data: message.data });
    return true;
  }
  
  if (message.action === 'checkLinkedInPage') {
    if (sender.tab) {
      const isLinkedIn = sender.tab.url?.includes('linkedin.com');
      sendResponse({ isLinkedIn });
    }
    return true;
  }
  
  if (message.action === 'sendEmail') {
    fetch(`${API_URL}/send-email`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        emailId: message.emailId,
        emailBody: message.emailBody,
        subject: message.subject || '',
        includeResume: message.includeResume,
        scheduleSend: message.scheduleSend || false
      })
    })
    .then(response => response.json())
    .then(data => {
      console.log("Email sent:", data);
      sendResponse({ success: data.success, message: data.message });
    })
    .catch(err => {
      console.error("Error sending email:", err);
      sendResponse({ success: false, error: err.message });
    });
    
    return true;
  }
  
  sendResponse({ success: false, error: 'Unknown action' });
  return true;
});

// Listen for tab updates to detect LinkedIn navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url?.includes('linkedin.com')) {
    chrome.tabs.sendMessage(tabId, { action: 'pageReady' }).catch(() => {
      // Content script might not be ready yet, ignore error
    });
  }
});
