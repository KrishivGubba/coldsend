console.log("ColdSend: content script active");



function getText(selector) {
  const el = document.querySelector(selector);
  return el ? el.textContent.trim() : null;
}

function waitFor(selector, timeout = 5000) {
  return new Promise(resolve => {
    const start = performance.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (performance.now() - start >= timeout) return resolve(null);
      requestAnimationFrame(check);
    };
    check();
  });
}

/**
 * Clicks all "See more" buttons within a container (or the whole page)
 * @param {Element} container - Optional container to search within
 * @returns {Promise} Resolves after all buttons are clicked and content expands
 */
async function expandAllSeeMore(container = document) {
  let clickedCount = 0;
  
  const clickables = container.querySelectorAll('button, a, span[role="button"]');
  
  for (const el of clickables) {
    const text = el.textContent.trim().toLowerCase();
    
    // Skip "see less" - already expanded
    if (text.includes('see less') || text.includes('show less')) {
      continue;
    }
    
    if (text.includes('see more') || text.includes('show more')) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        // Check if element is still in viewport/attached
        if (!document.body.contains(el)) continue;
        
        try {
          // Force focus first - helps with LinkedIn's event handlers
          el.focus();
          await new Promise(r => setTimeout(r, 50));
          el.click();
          clickedCount++;
          // Longer delay - give LinkedIn time to process
          await new Promise(r => setTimeout(r, 200));
        } catch (e) {
          console.log('Click failed:', e);
        }
      }
    }
  }
  
  return clickedCount;
}

/**
 * Extracts the About section text from a LinkedIn profile page.
 * Handles both collapsed and expanded states.
 * @returns {string|null} The about text, or null if not found
 */
function getAboutSection() {
  // Method 1: Find the About section by its id
  const aboutById = document.getElementById('about');
  if (aboutById) {
    // The actual content is in a sibling or nearby container
    const section = aboutById.closest('section');
    if (section) {
      // Look for the text content container
      // LinkedIn often uses a span with visually-hidden for full text
      const hiddenSpan = section.querySelector('span.visually-hidden');
      if (hiddenSpan && hiddenSpan.textContent.trim().length > 50) {
        return hiddenSpan.textContent.trim();
      }
      
      // Otherwise get the visible text from the main content div
      const contentDiv = section.querySelector('.display-flex.full-width');
      if (contentDiv) {
        return contentDiv.textContent.trim();
      }
      
      // Fallback: get all text from section, excluding the header
      const allText = section.textContent.trim();
      // Remove "About" header text
      return allText.replace(/^About\s*/i, '').trim();
    }
  }

  // Method 2: Find by section header text
  const allSections = document.querySelectorAll('section');
  for (const section of allSections) {
    const header = section.querySelector('h2, [class*="section-title"]');
    if (header && /^about$/i.test(header.textContent.trim())) {
      // Found the About section by header
      const hiddenSpan = section.querySelector('span.visually-hidden');
      if (hiddenSpan && hiddenSpan.textContent.trim().length > 50) {
        return hiddenSpan.textContent.trim();
      }
      
      // Get content excluding the header
      const clone = section.cloneNode(true);
      const headerInClone = clone.querySelector('h2, [class*="section-title"]');
      if (headerInClone) headerInClone.remove();
      return clone.textContent.trim();
    }
  }

  // Method 3: Look for aria-label containing "about"
  const aboutSection = document.querySelector('section[aria-label*="About" i]');
  if (aboutSection) {
    const hiddenSpan = aboutSection.querySelector('span.visually-hidden');
    if (hiddenSpan) {
      return hiddenSpan.textContent.trim();
    }
    return aboutSection.textContent.replace(/^About\s*/i, '').trim();
  }

  return null;
}

function expandConnectModal(firstName, lastName) {
  const fullName = `${firstName} ${lastName}`;

  // Query all buttons and all divs
  const buttons = document.querySelectorAll('button');
  const divs = document.querySelectorAll('div');

  // Filter buttons
  const filteredButtons = Array.from(buttons).filter(btn => {
    const ariaLabel = btn.getAttribute('aria-label');
    return ariaLabel && ariaLabel.toLowerCase() === `invite ${fullName.toLowerCase()} to connect`;
  });

  // Filter divs
  const filteredDivs = Array.from(divs).filter(div => {
    const ariaLabel = div.getAttribute('aria-label');
    return ariaLabel && ariaLabel.toLowerCase() === `invite ${fullName.toLowerCase()} to connect`;
  });

  // Combine both arrays and return
  let allElems = [...filteredButtons, ...filteredDivs];

  allElems[0].click();

  // Wait a second and a half, then click the first "Add a note" button available
  setTimeout(() => {
    const addNoteBtn = document.querySelector('button[aria-label="Add a note"]');
    if (addNoteBtn) addNoteBtn.click();
  }, 750);
}


/**
 * Extracts all visible experiences from a LinkedIn profile page.
 * @returns {Array} Array of experience objects with title, company, duration, location, description
 */
function getExperiences() {
  const experiences = [];
  
  // Find the Experience section
  const expSection = document.getElementById('experience')?.closest('section');
  if (!expSection) {
    // Fallback: find by header text
    const allSections = document.querySelectorAll('section');
    for (const section of allSections) {
      const header = section.querySelector('h2');
      if (header && /^experience$/i.test(header.textContent.trim())) {
        return extractExperiencesFromSection(section);
      }
    }
    return experiences;
  }
  
  return extractExperiencesFromSection(expSection);
}

/**
 * Helper to extract experiences from a section element
 */
function extractExperiencesFromSection(section) {
  const experiences = [];
  
  // Experience items are typically in list items within the section
  // LinkedIn uses <li> elements with specific classes
  const items = section.querySelectorAll('li.artdeco-list__item');
  
  // If no items found with that class, try broader selectors
  const expItems = items.length > 0 
    ? items 
    : section.querySelectorAll(':scope > div > ul > li');
  
  for (const item of expItems) {
    const exp = {};
    
    // Get all text spans - LinkedIn structures data in nested divs/spans
    const allSpans = item.querySelectorAll('span[aria-hidden="true"]');
    const texts = Array.from(allSpans)
      .map(s => s.textContent.trim())
      .filter(t => t.length > 0 && t.length < 200); // Filter out empty and super long strings
    
    if (texts.length === 0) continue;
    
    // First visible span is usually the job title
    // Look for the main title element
    const titleEl = item.querySelector('div.display-flex.align-items-center span[aria-hidden="true"]') 
      || item.querySelector('.t-bold span[aria-hidden="true"]');
    
    if (titleEl) {
      exp.title = titleEl.textContent.trim();
    } else if (texts[0]) {
      exp.title = texts[0];
    }
    
    // Company name - usually has a specific pattern or is a link
    const companyLink = item.querySelector('a[data-field="experience_company_logo"]');
    if (companyLink) {
      const companySpan = companyLink.querySelector('span[aria-hidden="true"]');
      if (companySpan) {
        exp.company = companySpan.textContent.trim();
      }
    }
    
    // If no company found via link, look for secondary text
    if (!exp.company) {
      const secondaryText = item.querySelector('.t-14.t-normal span[aria-hidden="true"]');
      if (secondaryText) {
        exp.company = secondaryText.textContent.trim();
      } else if (texts[1]) {
        exp.company = texts[1];
      }
    }
    
    // Duration - usually contains date ranges with "·" or "-"
    const durationMatch = texts.find(t => 
      /\d{4}/.test(t) && (/present/i.test(t) || /-/.test(t) || /·/.test(t))
    );
    if (durationMatch) {
      exp.duration = durationMatch;
    }
    
    // Location - usually contains common location indicators
    const locationMatch = texts.find(t => 
      /,/.test(t) && (/remote/i.test(t) || /city/i.test(t) || /states/i.test(t) || t.split(',').length >= 2)
      && !/\d{4}/.test(t) // not a date
    );
    if (locationMatch) {
      exp.location = locationMatch;
    }
    
    // Description - extract job description text
    exp.description = extractDescription(item, exp);
    
    // Only add if we have at least a title
    if (exp.title) {
      experiences.push(exp);
    }
  }
  
  // Deduplicate by title+company combo (LinkedIn sometimes has nested structures)
  const seen = new Set();
  return experiences.filter(exp => {
    const key = `${exp.title}|${exp.company || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Extracts the description text from an experience item
 */
function extractDescription(item, exp) {
  // Method 1: Look for visually-hidden span with full description
  const hiddenSpans = item.querySelectorAll('span.visually-hidden');
  for (const span of hiddenSpans) {
    const text = span.textContent.trim();
    // Description is usually longer and doesn't match title/company/duration
    if (text.length > 50 && 
        text !== exp.title && 
        text !== exp.company && 
        !text.includes(exp.duration || '___none___')) {
      return text;
    }
  }
  
  // Method 2: Look for inline-show/whitespace-pre-wrap elements (common for descriptions)
  const descContainers = item.querySelectorAll('.inline-show-more-text, [class*="whitespace-pre-wrap"]');
  for (const container of descContainers) {
    const text = container.textContent.trim();
    if (text.length > 30) {
      return text;
    }
  }
  
  // Method 3: Look for list items within the experience (bullet points)
  const bulletList = item.querySelector('ul.pvs-list');
  if (bulletList) {
    const bullets = bulletList.querySelectorAll('li');
    const bulletTexts = Array.from(bullets)
      .map(li => {
        const span = li.querySelector('span[aria-hidden="true"]');
        return span ? span.textContent.trim() : li.textContent.trim();
      })
      .filter(t => t.length > 10);
    
    if (bulletTexts.length > 0) {
      return bulletTexts.join('\n• ');
    }
  }
  
  // Method 4: Look for any div with substantial text that's not already captured
  const allDivs = item.querySelectorAll('div');
  for (const div of allDivs) {
    // Skip if it contains nested experience items
    if (div.querySelector('li.artdeco-list__item')) continue;
    
    const text = div.textContent.trim();
    // Check if it's a description-like text (longer, not matching other fields)
    if (text.length > 100 && 
        !text.startsWith(exp.title || '') &&
        !text.startsWith(exp.company || '') &&
        !/^\w+ \d{4} -/.test(text)) { // not starting with date
      
      // Clean up: remove title, company, duration from the text
      let cleaned = text;
      if (exp.title) cleaned = cleaned.replace(exp.title, '');
      if (exp.company) cleaned = cleaned.replace(exp.company, '');
      if (exp.duration) cleaned = cleaned.replace(exp.duration, '');
      if (exp.location) cleaned = cleaned.replace(exp.location, '');
      
      cleaned = cleaned.replace(/\s+/g, ' ').trim();
      
      // Only return if there's substantial text left
      if (cleaned.length > 50) {
        return cleaned;
      }
    }
  }
  
  return null;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  if (message.action === "getNameAndHeadline") {

    waitFor("h1").then(h1 => {
      if (!h1) {
        sendResponse({ success: false, error: "No profile data loaded" });
        return;
      }

      const name = getText("h1");
      const headline = getText(".text-body-medium.break-words");
      sendResponse({ success: true, data: { name, headline } });
    }).catch(err => {
      console.error("Error in getNameAndHeadline:", err);
      sendResponse({ success: false, error: "Extraction failed" });
    });

    return true;
  }

  if (message.action === "sendConnectionRequest") {
    const { message: connectionMessage, name } = message;
    
    // Parse name into first and last
    const nameParts = name.split(' ');
    const firstName = nameParts[0];
    const lastName = nameParts.slice(1).join(' ');
    
    console.log("ColdSend: Opening connection modal for", firstName, lastName);
    
    // Open the modal
    expandConnectModal(firstName, lastName);
    
    // Wait for the textarea to appear and populate it
    setTimeout(() => {
      // LinkedIn's connection note textarea
      const textarea = document.querySelector('textarea[name="message"]') || 
                       document.querySelector('#custom-message') ||
                       document.querySelector('textarea.connect-button-send-invite__custom-message');
      
      if (textarea) {
        textarea.focus();
        textarea.value = connectionMessage;
        // Trigger input event so LinkedIn registers the change
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        console.log("ColdSend: Populated connection message");
        sendResponse({ success: true });
      } else {
        console.error("ColdSend: Could not find connection textarea");
        sendResponse({ success: false, error: "Textarea not found" });
      }
    }, 1500); // Wait for modal animation
    
    return true;
  }

  if (message.action === "captureProfile") {
    console.log("ColdSend: Capturing profile");
    
    waitFor("h1").then(async (h1) => {
      if (!h1) {
        sendResponse({ success: false, error: "No profile detected" });
        return;
      }

      // Expand all "see more" buttons on the page first
      console.log("ColdSend: Expanding all sections...");
      
      // we're running this 10 times just to make sure all sections are expanded, one time isn't enough for some reason
      for (let i = 0; i < 10; i++) {
        await expandAllSeeMore();
      }

      const name = getText("h1");
      const headline = getText(".text-body-medium.break-words");
      const about = getAboutSection();
      const experiences = getExperiences();
      const profileUrl = window.location.href;

      console.log("Captured profile:", { name, headline, about, experiences, profileUrl });
      
      // Send to background script to generate email
      // chrome.runtime.sendMessage({
      //   action: 'generateEmail',
      //   data: { name, headline, about, experiences }
      // }, (response) => {
      //   if (response?.success) {
      //     console.log("Generated email:", response.email);
      //   } else {
      //     console.error("Email generation failed:", response?.error);
      //   }
      // });

      sendResponse({ 
        success: true, 
        data: { name, headline, about, experiences, profileUrl } 
      });
    }).catch(err => {
      console.error("Error in captureProfile:", err);
      sendResponse({ success: false });
    });

    return true;
  }

});
