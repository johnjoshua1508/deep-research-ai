// Initialize variables
let socket

// Try to initialize Socket.IO if available
try {
  // Import Socket.IO client library
  const io = require("socket.io-client")
  socket = io()

  // Socket.io event listeners
  socket.on("connect", () => {
    console.log("Connected to server")
  })

  socket.on("research_started", (data) => {
    console.log("Research started:", data)
    handleResearchStarted(data)
  })

  socket.on("research_progress", (data) => {
    if (currentChatId !== data.chat_id) return
    handleResearchProgress(data)
  })

  socket.on("research_complete", (data) => {
    handleResearchComplete(data.chat_id, data)
  })

  socket.on("research_stopped", (data) => {
    if (currentChatId !== data.chat_id) return
    handleResearchStopped(data)
  })
} catch (e) {
  console.warn("Socket.IO not available, falling back to AJAX polling")
  socket = null
}

// DOM Elements
const chatHistory = document.getElementById("chat-history")
const chatMessages = document.getElementById("chat-messages")
const currentChatTitle = document.getElementById("current-chat-title")
const queryInput = document.getElementById("query-input")
const sendQueryBtn = document.getElementById("send-query-btn")
const newChatBtn = document.getElementById("new-chat-btn")
const modelSelect = document.getElementById("model-select")
const modalModelSelect = document.getElementById("modal-model-select")
const settingsModal = document.getElementById("settings-modal")
const closeSettingsBtn = document.getElementById("close-settings-btn")
const saveSettingsBtn = document.getElementById("save-settings-btn")
const researchProgressContainer = document.getElementById("research-progress-container")
const researchProgressBar = document.getElementById("research-progress-bar")
const researchProgressText = document.getElementById("research-progress-text")
const references = document.getElementById("references")
const stopResearchBtn = document.getElementById("stop-research-btn")
const settingsBtn = document.getElementById("settings-btn")

// State
let currentChatId = null
let activeResearch = false
let statusPollingInterval = null

// Add handler functions for Socket.IO events
function handleResearchStarted(data) {
  currentChatId = data.chat_id
  activeResearch = true

  // Update UI
  researchProgressContainer.classList.remove("hidden")
  researchProgressBar.style.width = "5%"
  researchProgressText.textContent = "Starting research..."

  // Clear previous references
  references.innerHTML = '<p class="text-sm text-gray-600">Searching for references...</p>'

  // Update chat messages
  chatMessages.innerHTML = `
    <div class="mb-4">
      <div class="font-semibold mb-2">Research Query:</div>
      <div class="p-3 bg-indigo-50 rounded-lg">${data.query}</div>
    </div>
    <div id="research-status" class="flex items-center justify-center p-4">
      <div class="spinner mr-3"></div>
      <div>Research in progress...</div>
    </div>
    <div id="analysis-container" class="mt-4 hidden"></div>
  `

  // Update chat title
  currentChatTitle.textContent = truncateText(data.query, 40)

  // Add to chat history if not already there
  addChatToHistory(data.chat_id, data.query)

  // Show stop button when research starts
  document.getElementById("stop-research-btn").classList.remove("hidden")

  // Start polling for status updates
  startStatusPolling(data.chat_id)
}

function handleResearchProgress(data) {
  console.log("Research progress:", data)

  // Update progress bar
  researchProgressBar.style.width = `${data.progress}%`
  researchProgressText.textContent = data.message

  // Update research status
  const researchStatus = document.getElementById("research-status")
  if (researchStatus) {
    researchStatus.innerHTML = `
      <div class="spinner mr-3"></div>
      <div>${data.message}</div>
    `
  }
}

function handleResearchStopped(data) {
  console.log("Research stopped:", data)
  activeResearch = false
  clearInterval(statusPollingInterval)

  // Update UI to show research was stopped
  const researchStatus = document.getElementById("research-status")
  if (researchStatus) {
    researchStatus.innerHTML = `
      <div class="text-yellow-600 font-semibold">
        <i class="fas fa-stop-circle mr-2"></i>
        Research stopped
      </div>
    `
  }

  // Update progress bar
  researchProgressBar.style.width = "0%"
  researchProgressText.textContent = "Research stopped"

  // Hide stop button when research is stopped
  stopResearchBtn.classList.add("hidden")
}

// Load initial data
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing app...")
  loadChats()
  loadSettings()

  // Event listeners
  sendQueryBtn.addEventListener("click", startResearch)
  newChatBtn.addEventListener("click", createNewChat)
  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"))
  saveSettingsBtn.addEventListener("click", saveSettings)
  stopResearchBtn.addEventListener("click", stopResearch)
  settingsBtn.addEventListener("click", () => {
    const modelSelect = document.getElementById("modal-model-select")
    const modelDescription = document.getElementById("model-description")

    // Update model description
    modelDescription.textContent = MODEL_DESCRIPTIONS[modelSelect.value] || ""

    // Show modal
    document.getElementById("settings-modal").classList.remove("hidden")
  })

  // Enter key in input
  queryInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      startResearch()
    }
  })

  console.log("Event listeners initialized")

  // Restore active chat on page load
  const activeChat = localStorage.getItem("activeChat")
  if (activeChat) {
    setTimeout(() => loadChat(activeChat), 100) // Add small delay to ensure chat history is loaded
  }

  // Update model description on initial load
  const modelDescription = document.getElementById("model-description")
  modelDescription.textContent = MODEL_DESCRIPTIONS[modalModelSelect.value] || ""

  // Add change event listener for model select
  document.getElementById("modal-model-select").addEventListener("change", (e) => {
    const modelDescription = document.getElementById("model-description")
    modelDescription.textContent = MODEL_DESCRIPTIONS[e.target.value] || ""
  })

  // Settings modal event listeners
  settingsBtn.addEventListener("click", () => {
    const modelSelect = document.getElementById("modal-model-select")
    const modelDescription = document.getElementById("model-description")

    // Update model description
    modelDescription.textContent = MODEL_DESCRIPTIONS[modelSelect.value] || ""

    // Show modal
    document.getElementById("settings-modal").classList.remove("hidden")
  })

  // Close modal on cancel
  document.getElementById("cancel-settings-btn").addEventListener("click", () => {
    settingsModal.classList.add("hidden")
  })

  // Close modal on X button
  closeSettingsBtn.addEventListener("click", () => {
    settingsModal.classList.add("hidden")
  })

  // Save settings
  saveSettingsBtn.addEventListener("click", saveSettings)
})

// Functions
function startResearch() {
  console.log("startResearch called")
  const query = queryInput.value.trim()
  if (!query) {
    console.log("Query is empty, not starting research")
    return
  }

  if (activeResearch) {
    if (!confirm("Research is already in progress. Do you want to stop it and start a new one?")) {
      return
    }
    stopResearch()
  }

  // Hide search container and show disclaimer
  document.getElementById("search-container").classList.add("hidden")
  document.getElementById("ai-disclaimer").classList.remove("hidden")

  console.log("Starting research with query:", query)

  // Hide send button and show stop button
  sendQueryBtn.classList.add("hidden")
  stopResearchBtn.classList.remove("hidden")

  // Start research via API
  fetch("/api/research/start", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  })
    .then((response) => {
      console.log("Research start response status:", response.status)
      return response.json()
    })
    .then((data) => {
      console.log("Research started successfully:", data)
      currentChatId = data.chat_id
      activeResearch = true

      // Update UI
      researchProgressContainer.classList.remove("hidden")
      researchProgressBar.style.width = "5%"
      researchProgressText.textContent = "Starting research..."

      // Clear previous references
      references.innerHTML = '<p class="text-sm text-gray-600">Searching for references...</p>'

      // Update chat messages
      chatMessages.innerHTML = `
                <div class="mb-4">
                    <div class="font-semibold mb-2">Research Query:</div>
                    <div class="p-3 bg-indigo-50 rounded-lg">${query}</div>
                </div>
                <div id="research-status" class="flex items-center justify-center p-4">
                    <div class="spinner mr-3"></div>
                    <div>Research in progress...</div>
                </div>
                <div id="analysis-container" class="mt-4 hidden"></div>
            `

      // Update chat title
      currentChatTitle.textContent = truncateText(query, 40)

      // Add to chat history if not already there
      addChatToHistory(data.chat_id, query)

      // Start polling for status updates
      startStatusPolling(data.chat_id)
    })
    .catch((error) => {
      console.error("Error starting research:", error)
      alert("Error starting research. Please try again.")
      // Show send button and hide stop button on error
      sendQueryBtn.classList.remove("hidden")
      stopResearchBtn.classList.add("hidden")
    })

  // Clear input
  queryInput.value = ""
}

function startStatusPolling(chatId) {
  // Clear any existing interval
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval)
  }

  // Set up polling interval (every 2 seconds)
  statusPollingInterval = setInterval(() => {
    if (!activeResearch) {
      clearInterval(statusPollingInterval)
      return
    }

    fetch(`/api/research/status/${chatId}`)
      .then((response) => response.json())
      .then((status) => {
        // Update progress
        updateResearchProgress(status)

        // Check if research is completed
        if (status.completed) {
          handleResearchComplete(chatId, status)
        }
      })
      .catch((error) => {
        console.error("Error polling status:", error)
      })
  }, 2000)
}

function updateResearchProgress(status) {
  // Update progress bar
  researchProgressBar.style.width = `${status.progress}%`
  researchProgressText.textContent = status.message

  // Update research status
  const researchStatus = document.getElementById("research-status")
  if (researchStatus) {
    researchStatus.innerHTML = `
            <div class="spinner mr-3"></div>
            <div>${status.message}</div>
        `
  }

  // Update references if available
  if (status.references && status.references.length > 0) {
    displayReferences(status.references)
  }

  // Display analysis if available
  if (status.analysis) {
    const analysisContainer = document.getElementById("analysis-container")
    if (analysisContainer) {
      displayAnalysis(status.analysis, status.references)
    }
  }
}

function stopResearch() {
  if (!currentChatId || !activeResearch) return

  // Stop research via API
  fetch(`/api/research/stop/${currentChatId}`, {
    method: "POST",
  })
    .then((response) => response.json())
    .then((data) => {
      activeResearch = false
      clearInterval(statusPollingInterval)

      // Update UI to show research was stopped
      const researchStatus = document.getElementById("research-status")
      if (researchStatus) {
        researchStatus.innerHTML = `
                    <div class="text-yellow-600 font-semibold">
                        <i class="fas fa-stop-circle mr-2"></i>
                        Research stopped
                    </div>
                `
      }

      // Update progress bar
      researchProgressBar.style.width = "0%"
      researchProgressText.textContent = "Research stopped"

      // Show send button and hide stop button
      sendQueryBtn.classList.remove("hidden")
      stopResearchBtn.classList.add("hidden")

      // Show search container and hide disclaimer
      document.getElementById("search-container").classList.remove("hidden")
      document.getElementById("ai-disclaimer").classList.add("hidden")
    })
    .catch((error) => {
      console.error("Error stopping research:", error)
      alert("Error stopping research. Please try again.")
    })
}

function createNewChat() {
  // If there's active research, confirm before stopping
  if (activeResearch) {
    if (!confirm("Research is in progress. Do you want to stop it and start a new chat?")) {
      return
    }
    stopResearch()
  }

  // Reset UI
  currentChatId = null
  activeResearch = false
  clearInterval(statusPollingInterval)

  chatMessages.innerHTML = `
    <div class="flex flex-col items-center justify-center h-full text-center text-gray-500">
      <i class="fas fa-search text-5xl mb-4 text-indigo-300"></i>
      <h3 class="text-xl font-semibold mb-2">Start a new research query</h3>
      <p class="max-w-md">Enter your research topic below and our AI agents will gather and analyze information from the web.</p>
    </div>
  `

  currentChatTitle.textContent = "New Research"

  // Reset progress and references
  researchProgressContainer.classList.add("hidden")
  references.innerHTML = '<p class="text-sm text-gray-500 italic">No references available</p>'

  // Show search container and hide disclaimer
  document.getElementById("search-container").classList.remove("hidden")
  document.getElementById("ai-disclaimer").classList.add("hidden")

  // Focus on input
  queryInput.focus()
}

function loadChats() {
  fetch("/api/chats")
    .then((response) => response.json())
    .then((chats) => {
      chatHistory.innerHTML = ""

      if (chats.length === 0) {
        chatHistory.innerHTML = '<p class="text-sm text-gray-500 italic">No chat history</p>'
        return
      }

      chats.forEach((chat) => {
        addChatToHistory(chat._id, chat.query, chat.status)
      })
    })
    .catch((error) => {
      console.error("Error loading chats:", error)
      chatHistory.innerHTML = '<p class="text-sm text-red-500">Error loading chat history</p>'
    })
}

function addChatToHistory(id, query, status = "in_progress") {
  // Check if chat already exists in history
  const existingChat = document.querySelector(`.chat-item[data-id="${id}"]`)
  if (existingChat) {
    existingChat.classList.add("active")
    return
  }

  const chatItem = document.createElement("div")
  chatItem.className = `chat-item p-2 rounded cursor-pointer ${currentChatId === id ? "active" : ""}`
  chatItem.setAttribute("data-id", id)
  chatItem.setAttribute("data-status", status)

  chatItem.innerHTML = `
    <div class="text-sm font-medium truncate">${truncateText(query, 25)}</div>
    <div class="flex items-center text-xs text-gray-500 mt-1">
      <i class="fas ${status === "completed" ? "fa-check-circle text-green-500" : "fa-spinner fa-spin text-indigo-500"} mr-1"></i>
      <span>${status === "completed" ? "Completed" : "In progress"}</span>
    </div>
  `

  chatItem.addEventListener("click", () => loadChat(id))

  // Add to the beginning of the list
  if (chatHistory.firstChild) {
    chatHistory.insertBefore(chatItem, chatHistory.firstChild)
  } else {
    chatHistory.appendChild(chatItem)
  }
}

function updateChatInHistory(id, status) {
  const chatItem = document.querySelector(`.chat-item[data-id="${id}"]`)
  if (chatItem) {
    chatItem.setAttribute("data-status", status)

    const statusElement = chatItem.querySelector(".text-xs")
    if (statusElement) {
      statusElement.innerHTML = `
        <i class="fas ${status === "completed" ? "fa-check-circle text-green-500" : "fa-spinner fa-spin text-indigo-500"} mr-1"></i>
        <span>${status === "completed" ? "Completed" : "In progress"}</span>
      `
    }
  }
}

function loadChat(id) {
  if (activeResearch) {
    if (!confirm("Research is in progress. Loading another chat will cancel the current research. Continue?")) {
      return
    }
    stopResearch()
  }

  // Update active chat in sidebar
  document.querySelectorAll(".chat-item").forEach((item) => {
    item.classList.remove("active")
  })

  const chatItem = document.querySelector(`.chat-item[data-id="${id}"]`)
  if (chatItem) {
    chatItem.classList.add("active")
    // Store active chat ID in localStorage
    localStorage.setItem("activeChat", id)
  }

  // Fetch chat data
  fetch(`/api/chat/${id}`)
    .then((response) => response.json())
    .then((chat) => {
      currentChatId = chat._id
      activeResearch = chat.status === "in_progress"

      // Update UI
      currentChatTitle.textContent = truncateText(chat.query, 40)

      // Update chat messages with proper formatting
      chatMessages.innerHTML = `
                <div class="mb-4">
                    <div class="font-semibold mb-2">Research Query:</div>
                    <div class="p-3 bg-indigo-50 rounded-lg">${chat.query}</div>
                </div>
            `

      if (chat.status === "in_progress") {
        chatMessages.innerHTML += `
                    <div id="research-status" class="flex items-center justify-center p-4">
                        <div class="spinner mr-3"></div>
                        <div>Research in progress...</div>
                    </div>
                    <div id="analysis-container" class="mt-4 hidden"></div>
                `

        // Show progress
        researchProgressContainer.classList.remove("hidden")
        researchProgressBar.style.width = "50%"
        researchProgressText.textContent = "Research in progress..."

        // Clear references
        references.innerHTML = '<p class="text-sm text-gray-600">Searching for references...</p>'

        // Show stop button
        stopResearchBtn.classList.remove("hidden")

        // Hide search container and show disclaimer
        document.getElementById("search-container").classList.add("hidden")
        document.getElementById("ai-disclaimer").classList.remove("hidden")

        // Start polling for status updates
        startStatusPolling(chat._id)
      } else {
        // Show completed research status
        chatMessages.innerHTML += `
                    <div id="research-status" class="flex items-center justify-center p-4">
                        <div class="text-green-600 font-semibold">
                            <i class="fas fa-check-circle mr-2"></i>
                            Research completed
                        </div>
                    </div>
                    <div id="analysis-container" class="mt-4"></div>
                `

        // Show progress as complete
        researchProgressContainer.classList.remove("hidden")
        researchProgressBar.style.width = "100%"
        researchProgressText.textContent = "Research completed"

        // Display references if available
        if (chat.references && chat.references.length > 0) {
          displayReferences(chat.references)
        } else {
          references.innerHTML = '<p class="text-sm text-gray-500 italic">No references available</p>'
        }

        // Display analysis if available
        if (chat.analysis) {
          displayAnalysis(chat.analysis, chat.references || [])
        }

        // Hide stop button
        stopResearchBtn.classList.add("hidden")
        // Show send button
        sendQueryBtn.classList.remove("hidden")

        // Hide search container and show disclaimer
        document.getElementById("search-container").classList.add("hidden")
        document.getElementById("ai-disclaimer").classList.remove("hidden")
      }
    })
    .catch((error) => {
      console.error("Error loading chat:", error)
      alert("Error loading chat. Please try again.")
    })
}

function displayReferences(refs) {
  if (!refs || refs.length === 0) {
    references.innerHTML = '<p class="text-sm text-gray-500 italic">No references available</p>'
    return
  }

  references.innerHTML = ""
  refs.forEach((ref, index) => {
    const refElement = document.createElement("div")
    refElement.className = "reference-item p-2 rounded mb-2 text-sm hover:bg-gray-50"

    // Check if URL is valid
    const isValidUrl = ref.url && ref.url !== "#" && !ref.url.includes("undefined")

    refElement.innerHTML = `
      <div class="font-medium">[${index + 1}] ${ref.title || "Untitled"}</div>
      ${
        isValidUrl
          ? `
          <a href="${ref.url}" target="_blank" 
             class="text-indigo-600 hover:underline text-xs block mt-1 flex items-center">
              ${truncateText(ref.url, 40)}
              <i class="fas fa-external-link-alt ml-1"></i>
          </a>
      `
          : `
          <span class="text-gray-400 text-xs block mt-1">URL not available</span>
      `
      }
    `
    references.appendChild(refElement)
  })
}

function processAnalysisWithCitations(analysis, refs) {
  if (!analysis) return ""

  // Replace citation patterns like [1], [2], etc.
  const citationRegex = /\[(\d+)\]/g
  return analysis.replace(citationRegex, (match, p1) => {
    const citationIndex = Number.parseInt(p1) - 1
    if (citationIndex >= 0 && citationIndex < refs.length) {
      return `<span class="citation" data-index="${citationIndex}">${match}</span>`
    }
    return match
  })
}

function loadSettings() {
  fetch("/api/settings")
    .then((response) => response.json())
    .then((settings) => {
      // Define the only supported models in the correct order
      const supportedModels = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma-7b-it"]

      // Force llama-3.3-70b-versatile as the default model
      const defaultModel = "llama-3.3-70b-versatile"
      settings.selected_model = defaultModel

      // Override available models to only use supported ones
      settings.available_models = supportedModels

      // Populate model select with only the supported models
      populateModelSelect(modalModelSelect, supportedModels, defaultModel)

      // Save the settings to ensure they persist
      saveSettings()
    })
    .catch((error) => {
      console.error("Error loading settings:", error)
      // Set default model even if settings fail to load
      const defaultModel = "llama-3.3-70b-versatile"
      const supportedModels = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma-7b-it"]
      populateModelSelect(modalModelSelect, supportedModels, defaultModel)
    })
}

function populateModelSelect(selectElement, models, selectedModel) {
  selectElement.innerHTML = ""

  models.forEach((model) => {
    const option = document.createElement("option")
    option.value = model
    option.textContent = model
    option.selected = model === selectedModel
    selectElement.appendChild(option)
  })
}

function saveSettings() {
  const selectedModel = modalModelSelect.value

  fetch("/api/settings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      selected_model: selectedModel,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      // Close modal
      settingsModal.classList.add("hidden")

      // Show success toast
      showToast("Model settings saved successfully")
    })
    .catch((error) => {
      console.error("Error saving settings:", error)
      showToast("Error saving settings. Please try again.", "error")
    })
}

// Add toast notification function
function showToast(message, type = "success") {
  const toast = document.getElementById("toast")
  const toastMessage = document.getElementById("toast-message")

  // Set message
  toastMessage.textContent = message

  // Update toast color based on type
  const toastDiv = toast.firstElementChild
  if (type === "error") {
    toastDiv.classList.remove("bg-green-500")
    toastDiv.classList.add("bg-red-500")
  } else {
    toastDiv.classList.remove("bg-red-500")
    toastDiv.classList.add("bg-green-500")
  }

  // Show toast
  toast.classList.remove("translate-y-full", "opacity-0")

  // Hide toast after duration
  setTimeout(() => {
    toast.classList.add("translate-y-full", "opacity-0")
  }, 3000)
}

function processAnalysisContent(text) {
  if (!text) return ""

  // Split into sections
  const sections = text.split(/\n\n+/)

  // Process each section
  return sections
    .map((section) => {
      section = section.trim()

      // Skip empty sections
      if (!section) return ""

      // Check if it's a main heading (all caps or followed by specific patterns)
      if (
        section.match(/^[A-Z][A-Z\s]+(?:\s+(?:and|&|\+)\s+[A-Z\s]+)*$/m) ||
        section.match(
          /^(?:Introduction|Current State and Challenges|Key Technologies and Methods|Implementation and Best Practices|Economic and Security Impact|Future Perspectives|Conclusion)/,
        )
      ) {
        return `<h2 class="text-2xl font-bold mt-8 mb-4 text-gray-900">${section}</h2>`
      }

      // Check if it's a citation
      if (section.match(/\[\d+\]/g)) {
        // Replace citations with styled spans
        section = section.replace(
          /\[(\d+)\]/g,
          (match, p1) => `<span class="citation" data-index="${Number.parseInt(p1) - 1}">${match}</span>`,
        )
      }

      // Regular paragraph with improved typography
      return `<div class="mb-6">
                <p class="text-gray-700 leading-relaxed">${section}</p>
            </div>`
    })
    .join("\n")
}

function displayAnalysis(analysis, references) {
  const analysisContainer = document.getElementById("analysis-container")
  if (!analysisContainer) return

  // Process analysis text
  let processedAnalysis = analysis || "Analysis not available"

  // Format the content
  processedAnalysis = processAnalysisContent(processedAnalysis)

  // Count words in the analysis (excluding HTML tags)
  const wordCount = analysis
    .replace(/<[^>]*>/g, "")
    .split(/\s+/)
    .filter((word) => word.length > 0).length

  // Validate references
  const validReferences = references.filter(
    (ref) => ref && ref.url && ref.url !== "#" && !ref.url.includes("undefined"),
  )

  analysisContainer.innerHTML = `
        <div class="font-semibold text-xl mb-4">Analysis Results</div>
        <div class="text-sm text-gray-500 mb-4">
            Word count: ${wordCount} words | References: ${validReferences.length} sources
        </div>
        <div class="analysis-content prose max-w-none">
            ${processedAnalysis}
        </div>
    `

  // Add citation click handlers
  document.querySelectorAll(".citation").forEach((citation) => {
    citation.addEventListener("click", () => {
      const index = Number.parseInt(citation.getAttribute("data-index"))
      if (index >= 0 && index < validReferences.length) {
        const url = validReferences[index].url
        if (url && url !== "#" && !url.includes("undefined")) {
          window.open(url, "_blank")
        } else {
          alert("Reference link is not available")
        }
      }
    })
  })
}

function handleResearchComplete(chatId, status) {
  activeResearch = false
  clearInterval(statusPollingInterval)

  // Update progress
  researchProgressBar.style.width = "100%"
  researchProgressText.textContent = "Research completed"

  // Show send button and hide stop button
  sendQueryBtn.classList.remove("hidden")
  stopResearchBtn.classList.add("hidden")

  // Remove spinner and update research status
  const researchStatus = document.getElementById("research-status")
  if (researchStatus) {
    researchStatus.innerHTML = `
            <div class="research-complete">
                <div class="text-green-600 font-semibold flex items-center">
                    <i class="fas fa-check-circle mr-2"></i>
                    Research completed
                </div>
            </div>
        `
  }

  // Display analysis
  const analysisContainer = document.getElementById("analysis-container")
  if (analysisContainer) {
    analysisContainer.classList.remove("hidden")

    // Get analysis from status
    const analysis = status.analysis

    // If no analysis in status, try to get it from the chat
    if (!analysis) {
      fetch(`/api/chat/${chatId}`)
        .then((response) => response.json())
        .then((chat) => {
          if (chat.analysis) {
            displayAnalysis(chat.analysis, status.references)
          } else {
            analysisContainer.innerHTML = `
                            <div class="text-red-600 font-semibold">
                                Analysis generation failed. Please try again.
                            </div>
                        `
          }
        })
        .catch((error) => {
          console.error("Error fetching analysis:", error)
          analysisContainer.innerHTML = `
                        <div class="text-red-600 font-semibold">
                            Error loading analysis. Please refresh the page.
                        </div>
                    `
        })
    } else {
      displayAnalysis(analysis, status.references)
    }
  }

  // Update chat in history
  updateChatInHistory(chatId, "completed")
}

// Add these model descriptions
const MODEL_DESCRIPTIONS = {
  "llama-3.3-70b-versatile":
    "A powerful and versatile language model optimized for research tasks. Provides comprehensive analysis with high accuracy.",
  "mixtral-8x7b-32768": "A balanced model with strong analytical capabilities. Good for general research tasks.",
  "gemma-7b-it": "A lightweight and efficient model. Ideal for quick research tasks with good accuracy.",
}

// Add event listener for stop button
document.getElementById("stop-research-btn").addEventListener("click", stopResearch)

document.getElementById("modal-model-select").addEventListener("change", (e) => {
  const modelDescription = document.getElementById("model-description")
  modelDescription.textContent = MODEL_DESCRIPTIONS[e.target.value] || ""
})

// Utility functions
function truncateText(text, maxLength) {
  if (!text) return ""
  return text.length > maxLength ? text.substring(0, maxLength) + "..." : text
}

