import { useState, useRef, useEffect } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000/api/stock'
const CHAT_API_URL = 'http://127.0.0.1:8000/api/chat'

const popularStocks = [
  { symbol: 'AAPL', name: 'Apple' },
  { symbol: 'GOOGL', name: 'Google' },
  { symbol: 'MSFT', name: 'Microsoft' },
  { symbol: 'TSLA', name: 'Tesla' },
  { symbol: 'RELIANCE.NS', name: 'Reliance' },
  { symbol: 'TCS.NS', name: 'TCS' },
  { symbol: 'INFY.NS', name: 'Infosys' },
  { symbol: 'HDFCBANK.NS', name: 'HDFC Bank' },
]

// Stock name to symbol mapping for natural language understanding
const stockMappings = {
  // US Stocks
  'apple': 'AAPL',
  'aapl': 'AAPL',
  'google': 'GOOGL',
  'googl': 'GOOGL',
  'alphabet': 'GOOGL',
  'microsoft': 'MSFT',
  'msft': 'MSFT',
  'tesla': 'TSLA',
  'tsla': 'TSLA',
  'amazon': 'AMZN',
  'amzn': 'AMZN',
  'meta': 'META',
  'facebook': 'META',
  'netflix': 'NFLX',
  'nflx': 'NFLX',
  'nvidia': 'NVDA',
  'nvda': 'NVDA',
  'amd': 'AMD',
  'intel': 'INTC',
  'intc': 'INTC',
  'ibm': 'IBM',
  'oracle': 'ORCL',
  'orcl': 'ORCL',
  'salesforce': 'CRM',
  'adobe': 'ADBE',
  'adbe': 'ADBE',
  'paypal': 'PYPL',
  'pypl': 'PYPL',
  'visa': 'V',
  'mastercard': 'MA',
  'jpmorgan': 'JPM',
  'jpm': 'JPM',
  'goldman': 'GS',
  'goldman sachs': 'GS',
  'bank of america': 'BAC',
  'bac': 'BAC',
  'walmart': 'WMT',
  'wmt': 'WMT',
  'coca cola': 'KO',
  'cocacola': 'KO',
  'coke': 'KO',
  'pepsi': 'PEP',
  'pepsico': 'PEP',
  'mcdonalds': 'MCD',
  'mcd': 'MCD',
  'disney': 'DIS',
  'dis': 'DIS',
  'boeing': 'BA',
  'ba': 'BA',
  'uber': 'UBER',
  'airbnb': 'ABNB',
  'spotify': 'SPOT',
  'zoom': 'ZM',
  'snap': 'SNAP',
  'snapchat': 'SNAP',
  'twitter': 'X',
  'x': 'X',

  // Indian Stocks (NSE)
  'tcs': 'TCS.NS',
  'tata consultancy': 'TCS.NS',
  'tata consultancy services': 'TCS.NS',
  'reliance': 'RELIANCE.NS',
  'ril': 'RELIANCE.NS',
  'reliance industries': 'RELIANCE.NS',
  'infosys': 'INFY.NS',
  'infy': 'INFY.NS',
  'hdfc': 'HDFCBANK.NS',
  'hdfc bank': 'HDFCBANK.NS',
  'hdfcbank': 'HDFCBANK.NS',
  'icici': 'ICICIBANK.NS',
  'icici bank': 'ICICIBANK.NS',
  'icicibank': 'ICICIBANK.NS',
  'sbi': 'SBIN.NS',
  'state bank': 'SBIN.NS',
  'state bank of india': 'SBIN.NS',
  'wipro': 'WIPRO.NS',
  'hcl': 'HCLTECH.NS',
  'hcl tech': 'HCLTECH.NS',
  'hcltech': 'HCLTECH.NS',
  'tech mahindra': 'TECHM.NS',
  'techm': 'TECHM.NS',
  'tatamotors': 'TATAMOTORS.NS',
  'tata motors': 'TATAMOTORS.NS',
  'tatasteel': 'TATASTEEL.NS',
  'tata steel': 'TATASTEEL.NS',
  'maruti': 'MARUTI.NS',
  'maruti suzuki': 'MARUTI.NS',
  'bajaj': 'BAJFINANCE.NS',
  'bajaj finance': 'BAJFINANCE.NS',
  'bajaj auto': 'BAJAJ-AUTO.NS',
  'kotak': 'KOTAKBANK.NS',
  'kotak bank': 'KOTAKBANK.NS',
  'kotak mahindra': 'KOTAKBANK.NS',
  'axis': 'AXISBANK.NS',
  'axis bank': 'AXISBANK.NS',
  'airtel': 'BHARTIARTL.NS',
  'bharti airtel': 'BHARTIARTL.NS',
  'bhartiartl': 'BHARTIARTL.NS',
  'asian paints': 'ASIANPAINT.NS',
  'asianpaint': 'ASIANPAINT.NS',
  'hindunilvr': 'HINDUNILVR.NS',
  'hindustan unilever': 'HINDUNILVR.NS',
  'hul': 'HINDUNILVR.NS',
  'itc': 'ITC.NS',
  'larsen': 'LT.NS',
  'larsen and toubro': 'LT.NS',
  'l&t': 'LT.NS',
  'lt': 'LT.NS',
  'sun pharma': 'SUNPHARMA.NS',
  'sunpharma': 'SUNPHARMA.NS',
  'dr reddy': 'DRREDDY.NS',
  'drreddy': 'DRREDDY.NS',
  'cipla': 'CIPLA.NS',
  'adani': 'ADANIENT.NS',
  'adani enterprises': 'ADANIENT.NS',
  'adani ports': 'ADANIPORTS.NS',
  'adani green': 'ADANIGREEN.NS',
  'zomato': 'ZOMATO.NS',
  'paytm': 'PAYTM.NS',
  'nykaa': 'NYKAA.NS',
  'ola': 'OLECTRA.NS',
  'policybazaar': 'POLICYBZR.NS',
}

// Parse natural language query and extract stock symbol
const parseQuery = (query) => {
  // If it already has .NS or .BO suffix, return as-is (uppercase)
  const upperQuery = query.toUpperCase().trim()
  if (/\.(NS|BO)$/i.test(upperQuery)) {
    return upperQuery
  }

  // Convert to lowercase and clean up
  let cleaned = query.toLowerCase().trim()

  // Remove common words/phrases (only alphanumeric words that can use word boundaries)
  const removeWords = [
    'stock', 'share', 'price', 'of', 'the', 'what', 'is', 'whats',
    'show', 'me', 'get', 'find', 'check', 'tell', 'give', 'current',
    'today', 'now', 'latest', 'live', 'real', 'time', 'realtime',
    'value', 'rate', 'cost', 'worth', 'trading', 'at', 'for', 'please',
    'stocks', 'shares', 'prices'
  ]

  // Remove special characters separately
  cleaned = cleaned.replace(/[?!.,'"]/g, ' ')

  for (const word of removeWords) {
    cleaned = cleaned.replace(new RegExp(`\\b${word}\\b`, 'gi'), ' ')
  }

  // Clean up extra spaces
  cleaned = cleaned.replace(/\s+/g, ' ').trim()

  // Check if the cleaned query matches any known stock (exact match)
  if (stockMappings[cleaned]) {
    return stockMappings[cleaned]
  }

  // Try to find partial matches - check if query contains stock name or vice versa
  for (const [name, symbol] of Object.entries(stockMappings)) {
    if (cleaned === name || cleaned.includes(name) || name.includes(cleaned)) {
      return symbol
    }
  }

  // Check each word individually
  const words = cleaned.split(' ')
  for (const word of words) {
    if (word && stockMappings[word]) {
      return stockMappings[word]
    }
  }

  // If nothing matched and it looks like a symbol (letters/numbers only), return as-is
  const symbolCandidate = cleaned.toUpperCase().replace(/\s+/g, '')
  if (/^[A-Z0-9-]+$/.test(symbolCandidate)) {
    return symbolCandidate
  }

  // Return the first word as uppercase as last resort
  return words[0]?.toUpperCase() || cleaned.toUpperCase()
}

function App() {
  const [query, setQuery] = useState('')
  const [stockData, setStockData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchedSymbol, setSearchedSymbol] = useState('')

  // Chatbot state
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: 'Hello! I can help you manage users in the database. Try asking:\n• "Show all users"\n• "Add user John with email john@test.com"\n• "Delete user 2"' }
  ])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatMessagesRef = useRef(null)

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight
    }
  }, [chatMessages])

  // Chat submit handler
  const handleChatSubmit = async (e) => {
    e.preventDefault()
    if (!chatInput.trim() || chatLoading) return

    const userMessage = chatInput.trim()
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setChatLoading(true)

    try {
      const response = await fetch(CHAT_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      })

      const data = await response.json()
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        toolUsed: data.tool_used
      }])
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      }])
    } finally {
      setChatLoading(false)
    }
  }

  const fetchStock = async (inputQuery) => {
    const searchQuery = inputQuery || query
    if (!searchQuery.trim()) {
      setError('Please enter a stock name or symbol')
      return
    }

    // Parse natural language query to get symbol
    const symbol = parseQuery(searchQuery)
    setSearchedSymbol(symbol)

    setLoading(true)
    setError(null)
    setStockData(null)

    try {
      const encodedSymbol = encodeURIComponent(symbol)
      const response = await fetch(`${API_URL}/${encodedSymbol}`)
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to fetch stock data')
      }
      const data = await response.json()
      setStockData(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    fetchStock()
  }

  const handleQuickSelect = (stockSymbol) => {
    setQuery(stockSymbol)
    fetchStock(stockSymbol)
  }

  const formatNumber = (num) => {
    if (num === 'N/A' || num === null || num === undefined) return 'N/A'
    if (num >= 1000000000) return (num / 1000000000).toFixed(2) + 'B'
    if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M'
    if (num >= 1000) return (num / 1000).toFixed(2) + 'K'
    return num.toLocaleString()
  }

  const formatPrice = (price, currency) => {
    if (price === 'N/A' || price === null || price === undefined) return 'N/A'
    const currencySymbol = currency === 'INR' ? '₹' : '$'
    return `${currencySymbol}${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return (
    <div className="app">
      <div className="container">
        <header className="header">
          <h1>Stock Price Checker</h1>
          <p className="subtitle">Ask in natural language - "TCS stock price", "Apple share", "Reliance"</p>
        </header>

        <form onSubmit={handleSubmit} className="search-form">
          <div className="input-group">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Try: TCS stock price, Apple share, Reliance..."
              className="search-input"
            />
            <button type="submit" className="search-btn" disabled={loading}>
              {loading ? (
                <span className="spinner"></span>
              ) : (
                'Search'
              )}
            </button>
          </div>
        </form>

        <div className="quick-access">
          <p className="quick-label">Quick Access:</p>
          <div className="quick-buttons">
            {popularStocks.map((stock) => (
              <button
                key={stock.symbol}
                onClick={() => handleQuickSelect(stock.symbol)}
                className="quick-btn"
                disabled={loading}
              >
                {stock.name}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="error-card">
            <span className="error-icon">!</span>
            <div>
              <p>{error}</p>
              {searchedSymbol && <p className="searched-symbol">Searched for: {searchedSymbol}</p>}
            </div>
          </div>
        )}

        {stockData && (
          <div className="stock-card">
            <div className="stock-header">
              <div className="stock-info">
                <h2 className="stock-symbol">{stockData.symbol}</h2>
                <p className="stock-name">{stockData.name}</p>
                <span className="stock-exchange">{stockData.exchange} • {stockData.market}</span>
              </div>
              <div className="stock-price-section">
                <p className="stock-price">{formatPrice(stockData.price, stockData.currency)}</p>
                <p className={`stock-change ${stockData.change >= 0 ? 'positive' : 'negative'}`}>
                  {stockData.change >= 0 ? '▲' : '▼'} {stockData.change >= 0 ? '+' : ''}{stockData.change?.toFixed(2)} ({stockData.change_percent >= 0 ? '+' : ''}{stockData.change_percent?.toFixed(2)}%)
                </p>
              </div>
            </div>

            <div className="stock-details">
              <div className="detail-item">
                <span className="detail-label">Day High</span>
                <span className="detail-value high">{formatPrice(stockData.day_high, stockData.currency)}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Day Low</span>
                <span className="detail-value low">{formatPrice(stockData.day_low, stockData.currency)}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Volume</span>
                <span className="detail-value">{formatNumber(stockData.volume)}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Market State</span>
                <span className={`detail-value market-state ${stockData.market_state?.toLowerCase()}`}>
                  {stockData.market_state}
                </span>
              </div>
            </div>
          </div>
        )}

        <footer className="footer">
          <p>Data provided by Yahoo Finance • Understands natural language queries</p>
        </footer>
      </div>

      {/* Chat Toggle Button */}
      <button
        className={`chat-toggle-btn ${isChatOpen ? 'active' : ''}`}
        onClick={() => setIsChatOpen(!isChatOpen)}
      >
        {isChatOpen ? '✕' : '💬'}
      </button>

      {/* Chat Panel */}
      {isChatOpen && (
        <div className="chat-panel">
          <div className="chat-header">
            <span className="chat-title">🤖 MCP Assistant</span>
            <span className="chat-subtitle">User Management</span>
          </div>

          <div className="chat-messages" ref={chatMessagesRef}>
            {chatMessages.map((msg, index) => (
              <div key={index} className={`chat-message ${msg.role}`}>
                <div className="message-content">
                  {msg.content.split('\n').map((line, i) => (
                    <span key={i}>{line}<br /></span>
                  ))}
                </div>
                {msg.toolUsed && (
                  <span className="tool-badge">🔧 {msg.toolUsed}</span>
                )}
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message assistant">
                <div className="message-content typing">
                  <span className="dot"></span>
                  <span className="dot"></span>
                  <span className="dot"></span>
                </div>
              </div>
            )}
          </div>

          <form onSubmit={handleChatSubmit} className="chat-input-form">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask about users..."
              className="chat-input"
              disabled={chatLoading}
            />
            <button type="submit" className="chat-send-btn" disabled={chatLoading || !chatInput.trim()}>
              ➤
            </button>
          </form>
        </div>
      )}
    </div>
  )
}

export default App
