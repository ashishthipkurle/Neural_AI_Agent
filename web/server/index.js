const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;
const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://localhost:8000';

// Middleware
app.use(cors());
app.use(express.json());

// API Routes
app.get('/api/status', async (req, res) => {
  try {
    // Forward to Python API
    const response = await fetch(`${PYTHON_API_URL}/api/status`);
    if (response.ok) {
      const data = await response.json();
      res.json({
        ...data,
        agent: 'My AI Agent',
        timestamp: new Date().toISOString(),
      });
    } else {
      throw new Error('Python API not available');
    }
  } catch (error) {
    // Fallback if Python API is down
    res.json({
      status: 'offline',
      agent: 'My AI Agent',
      timestamp: new Date().toISOString(),
      error: 'Python agent not running. Start with: python -m agent.api_server'
    });
  }
});

app.get('/api/info', (req, res) => {
  res.json({
    name: 'Humanoid Local AI Agent',
    version: '1.0.0',
    capabilities: ['vision', 'speech', 'memory', 'tools', 'browser', 'apps'],
  });
});

// Chat endpoint - forwards to Python Agent API
app.post('/api/chat', async (req, res) => {
  const { message } = req.body;

  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  try {
    // Forward to Python API (full agent with tools)
    const response = await fetch(`${PYTHON_API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      throw new Error(`Python API returned ${response.status}`);
    }

    const data = await response.json();
    res.json({
      response: data.response,
      status: data.status,
      action_taken: data.action_taken,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Python API error:', error.message);
    
    res.json({
      response: `Agent connection failed. Please ensure the Python API is running:\n\n  python -m agent.api_server\n\nError: ${error.message}`,
      status: 'error',
      timestamp: new Date().toISOString(),
    });
  }
});

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const response = await fetch(`${PYTHON_API_URL}/api/health`);
    const data = await response.json();
    res.json({ ...data, node_server: 'healthy' });
  } catch {
    res.json({ status: 'degraded', node_server: 'healthy', python_agent: 'offline' });
  }
});

// Start Server
app.listen(PORT, () => {
  console.log(`🚀 Node.js proxy running on http://localhost:${PORT}`);
  console.log(`🐍 Python API URL: ${PYTHON_API_URL}`);
  console.log(`\n📋 To start the full agent, run:`);
  console.log(`   python -m agent.api_server`);
});
