console.log('popup loaded');

let currentProfileData = null;
let currentProfileUrl = null;


// Bold selected text in contenteditable
function toggleBold() {
  document.execCommand('bold', false, null);
  document.getElementById('email-content').focus();
}

// Convert plain text to HTML (for generated emails)
function textToHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}

// Get HTML content from email editor
function getEmailHtml() {
  return document.getElementById('email-content').innerHTML;
}

// Set HTML content in email editor
function setEmailHtml(html) {
  document.getElementById('email-content').innerHTML = html;
}

// Get current preferences from checkboxes and inputs
function getPreferences() {
  return {
    includeResume: document.getElementById('include-resume').checked,
    includeCoffeeChat: document.getElementById('include-coffee').checked,
    customInstructions: document.getElementById('custom-instructions').value.trim()
  };
}

// Get storage key for current profile
function getStorageKey(url) {
  // Extract the profile path (e.g., "/in/john-doe")
  const match = url.match(/linkedin\.com(\/in\/[^/?]+)/);
  return match ? `coldsend_${match[1]}` : null;
}

// Save email data to storage
function saveEmailData(email, subject, recipientEmail) {
  if (!currentProfileUrl) return;
  
  const key = getStorageKey(currentProfileUrl);
  if (!key) return;
  
  // Get current values if not provided (use innerHTML for contenteditable)
  const emailValue = email !== undefined ? email : document.getElementById('email-content').innerHTML;
  const subjectValue = subject !== undefined ? subject : document.getElementById('email-subject').value;
  const recipientValue = recipientEmail !== undefined ? recipientEmail : document.getElementById('recipient-email').value;
  
  chrome.storage.local.set({
    [key]: {
      email: emailValue,
      subject: subjectValue,
      recipientEmail: recipientValue,
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
      
      console.log("called from generate email in popup")
      // Now generate the email via background script
      chrome.runtime.sendMessage({
        action: 'generateEmail',
        data: currentProfileData,
        preferences: getPreferences(),
        linkedinUrl: currentProfileUrl
      }, emailResponse => {
        resetButton();
        
        const emailSubject = document.getElementById('email-subject');
        const recipientEmail = document.getElementById('recipient-email');
        
        if (emailResponse?.success && emailResponse.email) {
          // Convert plain text response to HTML for contenteditable
          emailContent.innerHTML = textToHtml(emailResponse.email);
          emailSubject.value = emailResponse.subject || '';
          emailSection.classList.remove('hidden');
          // Auto-fill recipient email if Apollo found it
          if (emailResponse.apolloEmail) {
            recipientEmail.value = emailResponse.apolloEmail;
            updateSendButtonState();
            console.log("Apollo found email:", emailResponse.apolloEmail);
          } else if (emailResponse.apolloError) {
            console.log("Apollo error:", emailResponse.apolloError);
          }
          
          // Save all data including recipient email (save as HTML)
          saveEmailData(emailContent.innerHTML, emailResponse.subject || '', recipientEmail.value);
        } else {
          emailContent.innerHTML = "Failed to generate email. Please try again.";
          emailSubject.value = '';
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

// Copy email to clipboard (copies plain text version)
function copyEmail() {
  const emailContent = document.getElementById('email-content');
  const copyBtn = document.getElementById('copy-btn');
  
  // Get text content (strips HTML tags) for plain text copy
  navigator.clipboard.writeText(emailContent.innerText).then(() => {
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
  
  console.log("called from regen")
  chrome.runtime.sendMessage({
    action: 'generateEmail',
    data: currentProfileData,
    preferences: getPreferences(),
    linkedinUrl: currentProfileUrl
  }, response => {
    regenerateBtn.disabled = false;
    regenerateBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/>
      </svg>
      Regenerate
    `;
    
    const emailSubject = document.getElementById('email-subject');
    const recipientEmail = document.getElementById('recipient-email');
    
    if (response?.success && response.email) {
      // Convert plain text response to HTML for contenteditable
      emailContent.innerHTML = textToHtml(response.email);
      emailSubject.value = response.subject || '';
      
      // Auto-fill recipient email if Apollo found it
      if (response.apolloEmail && !recipientEmail.value) {
        recipientEmail.value = response.apolloEmail;
        updateSendButtonState();
      }
      
      // Save all data including recipient email (save as HTML)
      saveEmailData(emailContent.innerHTML, response.subject || '', recipientEmail.value);
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
  const emailContent = document.getElementById('email-content').innerHTML; // Send as HTML
  const emailSubject = document.getElementById('email-subject').value.trim();
  const scheduleSend = document.getElementById('schedule-send').checked;
  const sendBtn = document.getElementById('send-btn');
  
  if (!recipientEmail) return;
  
  sendBtn.disabled = true;
  const actionText = scheduleSend ? 'Scheduling...' : 'Sending...';
  sendBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    ${actionText}
  `;
  
  chrome.runtime.sendMessage({
    action: 'sendEmail',
    emailId: recipientEmail,
    emailBody: emailContent,
    subject: emailSubject,
    includeResume: getPreferences().includeResume,
    scheduleSend: scheduleSend
  }, response => {
    if (response?.success) {
      const successText = scheduleSend ? 'Scheduled!' : 'Sent!';
      sendBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        ${successText}
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

// Send connection request
function sendConnectionRequest() {
  const connectBtn = document.getElementById('connect-btn');
  
  connectBtn.disabled = true;
  connectBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    Generating...
  `;
  
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const tab = tabs[0];
    
    // First capture profile data if we don't have it
    if (!currentProfileData) {
      chrome.tabs.sendMessage(tab.id, { action: "captureProfile" }, response => {
        if (chrome.runtime.lastError || !response?.success) {
          console.error("Failed to capture profile");
          resetConnectButton();
          return;
        }
        currentProfileData = response.data;
        generateAndSendConnectionRequest(tab.id);
      });
    } else {
      generateAndSendConnectionRequest(tab.id);
    }
  });
}

function generateAndSendConnectionRequest(tabId) {
  const connectBtn = document.getElementById('connect-btn');
  
  // Generate connection message via background script
  chrome.runtime.sendMessage({
    action: 'generateConnectionMessage',
    data: currentProfileData,
    preferences: getPreferences()
  }, response => {
    if (response?.success && response.message) {
      // Send message to content script to open modal and populate
      chrome.tabs.sendMessage(tabId, { 
        action: "sendConnectionRequest",
        message: response.message,
        name: currentProfileData.name
      }, contentResponse => {
        resetConnectButton();
        
        if (contentResponse?.success) {
          connectBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Modal Opened!
          `;
          setTimeout(resetConnectButton, 2000);
        }
      });
    } else {
      resetConnectButton();
    }
  });
}

function resetConnectButton() {
  const connectBtn = document.getElementById('connect-btn');
  connectBtn.disabled = false;
  connectBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="8.5" cy="7" r="4"/>
      <line x1="20" y1="8" x2="20" y2="14"/>
      <line x1="23" y1="11" x2="17" y2="11"/>
    </svg>
    Send Connection Request
  `;
}

// Event listeners
document.getElementById('capture-btn').addEventListener('click', generateEmail);
document.getElementById('copy-btn').addEventListener('click', copyEmail);
document.getElementById('regenerate-btn').addEventListener('click', regenerateEmail);
document.getElementById('send-btn').addEventListener('click', sendEmail);
document.getElementById('recipient-email').addEventListener('input', updateSendButtonState);
document.getElementById('connect-btn').addEventListener('click', sendConnectionRequest);
document.getElementById('settings-btn').addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('oninstall_stuff/oninstall.html') });
});
document.getElementById('bold-btn').addEventListener('click', toggleBold);

// Save email when user edits the textarea, subject, or recipient email
document.getElementById('email-content').addEventListener('input', () => {
  saveEmailData();
});

document.getElementById('email-subject').addEventListener('input', () => {
  saveEmailData();
});

document.getElementById('recipient-email').addEventListener('input', () => {
  saveEmailData();
});


//on being loaded it's pulling the profile headline and name to show on the popup and then it's also checking to see if an email's already been written for this profile
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
        emailContent.innerHTML = savedData.email; // Load HTML content
        document.getElementById('email-subject').value = savedData.subject || '';
        emailSection.classList.remove('hidden');
        currentProfileData = savedData.profileData;
        
        // Restore recipient email if saved
        if (savedData.recipientEmail) {
          document.getElementById('recipient-email').value = savedData.recipientEmail;
          updateSendButtonState();
        }
        
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
