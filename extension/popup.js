console.log('popup loaded');

function captureProfile() {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const tab = tabs[0];
    chrome.tabs.sendMessage(tab.id, { action: "captureProfile" }, response => {
      console.log("Profile data response:", response);
    });
  });
}

document.getElementById('capture-btn').addEventListener('click', captureProfile);

document.addEventListener('DOMContentLoaded', () => {
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const profileSection = document.getElementById('profile-section');
  const notLinkedIn = document.getElementById('not-linkedin');

  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    const tab = tabs[0];

    // Check if user is on a LinkedIn profile page
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

    chrome.tabs.sendMessage(tab.id, { action: "getNameAndHeadline" }, response => {
      
      // FIRST: check for errors
      if (chrome.runtime.lastError) {
        console.warn("Content script error:", chrome.runtime.lastError.message);
        statusText.textContent = 'Error loading profile';
        return;
      }
      
      // THEN check if response is missing
      if (!response || !response.data) {
        console.warn("No response returned from content script.");
        statusText.textContent = 'No profile data';
        return;
      }

      console.log("Profile data response:", response);

      // Show the profile section
      profileSection.classList.remove('hidden');

      // Populate UI
      document.getElementById("profile-name").textContent = response.data.name || "(Unknown)";
      document.getElementById("profile-headline").textContent = response.data.headline || "(No headline)";
    });
  });
});
