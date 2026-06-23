const express = require('express');
const pg = require('pg');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// PostgreSQL connection
const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://energy_admin:energy_pass@localhost:5433/euro_energy'
});

app.use(cors());
app.use(express.static(path.join(__dirname, 'app')));

// API endpoint to get consumption data
app.get('/api/consumption', async (req, res) => {
  try {
    const query = `
      SELECT country, date, energy, energy_type 
      FROM raw_energy_consumption 
      WHERE date = (SELECT MAX(date) FROM raw_energy_consumption)
      ORDER BY country
    `;
    const result = await pool.query(query);
    
    // Group by country
    const data = {};
    result.rows.forEach(row => {
      if (!data[row.country]) {
        data[row.country] = {
          country: row.country,
          consumption: row.energy,
          date: row.date
        };
      }
    });
    
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database query failed' });
  }
});

// API endpoint to get generation data
app.get('/api/generation', async (req, res) => {
  try {
    const query = `
      SELECT country, date, energy, energy_type 
      FROM raw_energy_generation 
      WHERE date = (SELECT MAX(date) FROM raw_energy_generation)
      ORDER BY country, energy_type
    `;
    const result = await pool.query(query);
    
    // Group by country and energy type
    const data = {};
    result.rows.forEach(row => {
      if (!data[row.country]) {
        data[row.country] = {};
      }
      data[row.country][row.energy_type] = row.energy;
    });
    
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database query failed' });
  }
});

// DEBUG: Check database status
app.get('/api/debug/status', async (req, res) => {
  try {
    const consumer = await pool.query('SELECT COUNT(*) as count FROM raw_energy_consumption');
    const generator = await pool.query('SELECT COUNT(*) as count FROM raw_energy_generation');
    const latestConsumer = await pool.query('SELECT MAX(date) as latest FROM raw_energy_consumption');
    const latestGenerator = await pool.query('SELECT MAX(date) as latest FROM raw_energy_generation');
    
    res.json({
      consumption_rows: consumer.rows[0].count,
      generation_rows: generator.rows[0].count,
      latest_consumption_date: latestConsumer.rows[0].latest,
      latest_generation_date: latestGenerator.rows[0].latest
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database query failed', details: err.message });
  }
});

// DEBUG: Get all consumption data
app.get('/api/debug/consumption', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM raw_energy_consumption LIMIT 10');
    res.json({ rows: result.rows, count: result.rowCount });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Database query failed', details: err.message });
  }
});

// Serve index.html for root path
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'app', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
