console.log('popup loaded');

let currentProfileData = null;
let currentProfileUrl = null;

// Get current preferences from checkboxes
function getPreferences() {
  return {
    includeResume: document.getElementById('include-resume').checked,
    includeCoffeeChat: document.getElementById('include-coffee').checked
  };
}

// Get storage key for current profile
function getStorageKey(url) {
  // Extract the profile path (e.g., "/in/john-doe")
  const match = url.match(/linkedin\.com(\/in\/[^/?]+)/);
  return match ? `coldsend_${match[1]}` : null;
}

// Save email data to storage
function saveEmailData(email) {
  if (!currentProfileUrl) return;
  
  const key = getStorageKey(currentProfileUrl);
  if (!key) return;
  
  chrome.storage.local.set({
    [key]: {
      email: email,
      profileData: currentProfileData,
      timestamp: Date.now()
    }
  });
}

// Load saved email data
function loadEmailData(url, callback) {
  const key = getStorageKey(url);
  if (!key) {
    callback(null);
    return;
  }
  
  chrome.storage.local.get(key, result => {
    callback(result[key] || null);
  });
}

// Generate email from captured profile
function generateEmail() {
  const captureBtn = document.getElementById('capture-btn');
  const emailSection = document.getElementById('email-section');
  const emailContent = document.getElementById('email-content');
  
  // Show loading state
  captureBtn.disabled = true;
  captureBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    Generating...
  `;
  
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const tab = tabs[0];
    currentProfileUrl = tab.url;
    
    // First capture the profile
    chrome.tabs.sendMessage(tab.id, { action: "captureProfile" }, response => {
      if (chrome.runtime.lastError || !response?.success) {
        console.error("Failed to capture profile");
        resetButton();
        return;
      }
      
      currentProfileData = response.data;
      console.log("Profile captured:", currentProfileData);
      
      // Now generate the email via background script
      chrome.runtime.sendMessage({
        action: 'generateEmail',
        data: currentProfileData,
        preferences: getPreferences()
      }, emailResponse => {
        resetButton();
        
        if (emailResponse?.success && emailResponse.email) {
          emailContent.value = emailResponse.email;
          emailSection.classList.remove('hidden');
          saveEmailData(emailResponse.email);
        } else {
          emailContent.value = "Failed to generate email. Please try again.";
          emailSection.classList.remove('hidden');
        }
      });
    });
  });
}

function resetButton() {
  const captureBtn = document.getElementById('capture-btn');
  captureBtn.disabled = false;
  captureBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"/>
    </svg>
    Generate Email
  `;
}

// Copy email to clipboard
function copyEmail() {
  const emailContent = document.getElementById('email-content');
  const copyBtn = document.getElementById('copy-btn');
  
  navigator.clipboard.writeText(emailContent.value).then(() => {
    copyBtn.classList.add('success');
    copyBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      Copied!
    `;
    
    setTimeout(() => {
      copyBtn.classList.remove('success');
      copyBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy
      `;
    }, 2000);
  });
}

// Regenerate email with same profile data
function regenerateEmail() {
  if (!currentProfileData) {
    generateEmail();
    return;
  }
  
  const regenerateBtn = document.getElementById('regenerate-btn');
  const emailContent = document.getElementById('email-content');
  
  regenerateBtn.disabled = true;
  regenerateBtn.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    ...
  `;
  
  chrome.runtime.sendMessage({
    action: 'generateEmail',
    data: currentProfileData,
    preferences: getPreferences()
  }, response => {
    regenerateBtn.disabled = false;
    regenerateBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/>
      </svg>
      Regenerate
    `;
    
    if (response?.success && response.email) {
      emailContent.value = response.email;
      saveEmailData(response.email);
    }
  });
}

// Update send button state based on email input
function updateSendButtonState() {
  const recipientEmail = document.getElementById('recipient-email').value.trim();
  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = recipientEmail.length === 0;
}

// Send email
function sendEmail() {
  const recipientEmail = document.getElementById('recipient-email').value.trim();
  const emailContent = document.getElementById('email-content').value;
  const sendBtn = document.getElementById('send-btn');
  
  if (!recipientEmail) return;
  
  sendBtn.disabled = true;
  sendBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    Sending...
  `;
  
  chrome.runtime.sendMessage({
    action: 'sendEmail',
    emailId: recipientEmail,
    emailBody: emailContent
  }, response => {
    if (response?.success) {
      sendBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        Sent!
      `;
      
      setTimeout(() => {
        sendBtn.disabled = false;
        sendBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"/>
          </svg>
          Send Email
        `;
        updateSendButtonState();
      }, 2000);
    } else {
      sendBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        Failed
      `;
      
      setTimeout(() => {
        sendBtn.disabled = false;
        sendBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"/>
          </svg>
          Send Email
        `;
        updateSendButtonState();
      }, 2000);
    }
  });
}

// Event listeners
document.getElementById('capture-btn').addEventListener('click', generateEmail);
document.getElementById('copy-btn').addEventListener('click', copyEmail);
document.getElementById('regenerate-btn').addEventListener('click', regenerateEmail);
document.getElementById('send-btn').addEventListener('click', sendEmail);
document.getElementById('recipient-email').addEventListener('input', updateSendButtonState);

// Save email when user edits the textarea
document.getElementById('email-content').addEventListener('input', (e) => {
  saveEmailData(e.target.value);
});

document.addEventListener('DOMContentLoaded', () => {
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const profileSection = document.getElementById('profile-section');
  const notLinkedIn = document.getElementById('not-linkedin');
  const emailSection = document.getElementById('email-section');
  const emailContent = document.getElementById('email-content');

  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const tab = tabs[0];
    currentProfileUrl = tab.url;

    const isLinkedInProfile =
      tab && tab.url && /^https:\/\/.*linkedin\.com\/in\/.+/.test(tab.url);

    if (!isLinkedInProfile) {
      console.log('Not on a LinkedIn profile page.');
      statusDot.classList.add('inactive');
      statusText.textContent = 'Not on LinkedIn profile';
      notLinkedIn.classList.remove('hidden');
      return;
    }

    statusDot.classList.add('active');
    statusText.textContent = 'Active on LinkedIn';

    // Load any saved email for this profile
    loadEmailData(tab.url, savedData => {
      if (savedData && savedData.email) {
        emailContent.value = savedData.email;
        emailSection.classList.remove('hidden');
        currentProfileData = savedData.profileData;
        console.log("Loaded saved email for this profile");
      }
    });

    chrome.tabs.sendMessage(tab.id, { action: "getNameAndHeadline" }, response => {
      if (chrome.runtime.lastError) {
        console.warn("Content script error:", chrome.runtime.lastError.message);
        statusText.textContent = 'Error loading profile';
        return;
      }
      
      if (!response || !response.data) {
        console.warn("No response returned from content script.");
        statusText.textContent = 'No profile data';
        return;
      }

      console.log("Profile data response:", response);
      profileSection.classList.remove('hidden');
      document.getElementById("profile-name").textContent = response.data.name || "(Unknown)";
      document.getElementById("profile-headline").textContent = response.data.headline || "(No headline)";
    });
  });
});
