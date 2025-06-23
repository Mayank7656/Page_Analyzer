class PDFViewer {
  constructor() {
    this.currentPdf = null
    this.currentPage = 1
    this.totalPages = 0
    this.scale = 1.0
    this.isAdmin = false
    this.apiBase = "http://localhost:5000/api"

    this.init()
  }

  init() {
    this.setupEventListeners()
    this.loadPDFList()
    this.checkAuthStatus()
  }

  setupEventListeners() {
    // Login/Logout
    document.getElementById("loginBtn").addEventListener("click", () => {
      document.getElementById("loginModal").style.display = "block"
    })

    document.getElementById("logoutBtn").addEventListener("click", () => {
      this.logout()
    })

    document.getElementById("loginForm").addEventListener("submit", (e) => {
      e.preventDefault()
      this.login()
    })

    // PDF Viewer Controls
    document.getElementById("backBtn").addEventListener("click", () => {
      this.showPDFList()
    })

    document.getElementById("prevPage").addEventListener("click", () => {
      if (this.currentPage > 1) {
        this.currentPage--
        this.renderPage()
      }
    })

    document.getElementById("nextPage").addEventListener("click", () => {
      if (this.currentPage < this.totalPages) {
        this.currentPage++
        this.renderPage()
      }
    })

    document.getElementById("zoomIn").addEventListener("click", () => {
      this.scale *= 1.2
      this.renderPage()
    })

    document.getElementById("zoomOut").addEventListener("click", () => {
      this.scale /= 1.2
      this.renderPage()
    })

    // Modal close buttons
    document.querySelectorAll(".close").forEach((closeBtn) => {
      closeBtn.addEventListener("click", (e) => {
        e.target.closest(".modal").style.display = "none"
      })
    })

    // Close modal when clicking outside
    window.addEventListener("click", (e) => {
      if (e.target.classList.contains("modal")) {
        e.target.style.display = "none"
      }
    })
  }

  async loadPDFList() {
    try {
      const response = await fetch(`${this.apiBase}/pdfs`)
      const pdfs = await response.json()
      this.displayPDFList(pdfs)
    } catch (error) {
      console.error("Error loading PDF list:", error)
      this.showError("Failed to load PDF list")
    }
  }

  displayPDFList(pdfs) {
    const pdfList = document.getElementById("pdfList")
    pdfList.innerHTML = ""

    pdfs.forEach((pdf) => {
      const pdfItem = document.createElement("div")
      pdfItem.className = "pdf-item"
      pdfItem.innerHTML = `
                <div class="pdf-icon">📄</div>
                <h3>${pdf.name}</h3>
                <p>Size: ${this.formatFileSize(pdf.size)}</p>
            `
      pdfItem.addEventListener("click", () => this.openPDF(pdf.filename))
      pdfList.appendChild(pdfItem)
    })
  }

  async openPDF(filename) {
    try {
      // Track PDF access
      await fetch(`${this.apiBase}/track-access`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename }),
      })

      // Load and display PDF
      const pdfUrl = `${this.apiBase}/pdf/${filename}`
      const loadingTask = pdfjsLib.getDocument(pdfUrl)

      this.currentPdf = await loadingTask.promise
      this.totalPages = this.currentPdf.numPages
      this.currentPage = 1
      this.scale = 1.0

      this.showPDFViewer()
      this.renderPage()
    } catch (error) {
      console.error("Error opening PDF:", error)
      this.showError("Failed to open PDF")
    }
  }

  async renderPage() {
    if (!this.currentPdf) return

    try {
      const page = await this.currentPdf.getPage(this.currentPage)
      const canvas = document.getElementById("pdfCanvas")
      const context = canvas.getContext("2d")

      const viewport = page.getViewport({ scale: this.scale })
      canvas.height = viewport.height
      canvas.width = viewport.width

      const renderContext = {
        canvasContext: context,
        viewport: viewport,
      }

      await page.render(renderContext).promise
      this.updatePageInfo()
    } catch (error) {
      console.error("Error rendering page:", error)
    }
  }

  updatePageInfo() {
    document.getElementById("pageInfo").textContent = `Page ${this.currentPage} of ${this.totalPages}`

    document.getElementById("prevPage").disabled = this.currentPage <= 1
    document.getElementById("nextPage").disabled = this.currentPage >= this.totalPages
  }

  showPDFList() {
    document.getElementById("pdfListSection").style.display = "block"
    document.getElementById("pdfViewerSection").style.display = "none"
    document.getElementById("adminSection").style.display = this.isAdmin ? "block" : "none"
  }

  showPDFViewer() {
    document.getElementById("pdfListSection").style.display = "none"
    document.getElementById("pdfViewerSection").style.display = "block"
    document.getElementById("adminSection").style.display = "none"
  }

  async login() {
    const username = document.getElementById("username").value
    const password = document.getElementById("password").value

    try {
      const response = await fetch(`${this.apiBase}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      })

      const result = await response.json()

      if (result.success) {
        this.isAdmin = true
        localStorage.setItem("isAdmin", "true")
        this.updateAuthUI()
        document.getElementById("loginModal").style.display = "none"
        this.loadAnalytics()
      } else {
        this.showError("Invalid credentials")
      }
    } catch (error) {
      console.error("Login error:", error)
      this.showError("Login failed")
    }
  }

  logout() {
    this.isAdmin = false
    localStorage.removeItem("isAdmin")
    this.updateAuthUI()
    this.showPDFList()
  }

  checkAuthStatus() {
    this.isAdmin = localStorage.getItem("isAdmin") === "true"
    this.updateAuthUI()
    if (this.isAdmin) {
      this.loadAnalytics()
    }
  }

  updateAuthUI() {
    document.getElementById("loginBtn").style.display = this.isAdmin ? "none" : "block"
    document.getElementById("logoutBtn").style.display = this.isAdmin ? "block" : "none"
    document.getElementById("adminSection").style.display = this.isAdmin ? "block" : "none"
  }

  async loadAnalytics() {
    if (!this.isAdmin) return

    try {
      const response = await fetch(`${this.apiBase}/analytics`)
      const analytics = await response.json()
      this.displayAnalytics(analytics)
    } catch (error) {
      console.error("Error loading analytics:", error)
    }
  }

  displayAnalytics(analytics) {
    document.getElementById("totalViews").textContent = analytics.total_views
    document.getElementById("uniquePdfs").textContent = analytics.unique_pdfs
    document.getElementById("todayViews").textContent = analytics.today_views

    const tableBody = document.querySelector("#analyticsTable tbody")
    tableBody.innerHTML = ""

    analytics.pdf_stats.forEach((pdf) => {
      const row = document.createElement("tr")
      row.innerHTML = `
                <td>${pdf.filename}</td>
                <td>${pdf.total_opens}</td>
                <td>${new Date(pdf.last_accessed).toLocaleString()}</td>
                <td>
                    <button class="btn" onclick="pdfViewer.showPDFDetails('${pdf.filename}')">
                        View Details
                    </button>
                </td>
            `
      tableBody.appendChild(row)
    })
  }

  async showPDFDetails(filename) {
    try {
      const response = await fetch(`${this.apiBase}/pdf-details/${filename}`)
      const details = await response.json()

      document.getElementById("detailsTitle").textContent = `Access History: ${filename}`

      const content = document.getElementById("detailsContent")
      content.innerHTML = `
                <div class="access-history">
                    ${details.accesses
                      .map(
                        (access) => `
                        <div class="access-item">
                            <span>Access Time:</span>
                            <span>${new Date(access.timestamp).toLocaleString()}</span>
                        </div>
                    `,
                      )
                      .join("")}
                </div>
            `

      document.getElementById("detailsModal").style.display = "block"
    } catch (error) {
      console.error("Error loading PDF details:", error)
    }
  }

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  showError(message) {
    alert(message) // In production, use a better notification system
  }
}

// Initialize the PDF viewer when the page loads
const pdfViewer = new PDFViewer()
let currentPage = 1;
let startTime = Date.now();
let pageTimes = {};

const renderPDF = async () => {
    const pdf = await pdfjsLib.getDocument("/static/sample.pdf").promise;
    const page = await pdf.getPage(currentPage);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = document.getElementById('pdf-canvas');
    const context = canvas.getContext('2d');

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: context, viewport });

    startTime = Date.now();
};

const nextPage = () => {
    const duration = (Date.now() - startTime) / 1000;  // Convert to seconds
    if (!pageTimes[currentPage]) {
        pageTimes[currentPage] = [];
    }
    pageTimes[currentPage].push(duration);

    currentPage++;
    renderPDF();
};

// Track navigation
document.getElementById("next-btn").addEventListener("click", nextPage);
renderPDF();
