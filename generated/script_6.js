import React, { useState } from 'react';
import {
  Container,
  Box,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Grid,
  Paper
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/lab';
import AdapterDayjs from '@mui/lab/AdapterDayjs';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
dayjs.extend(duration);

function calculateAge(birthDate) {
  const now = dayjs();
  const diff = now.diff(birthDate, 'year');
  const months = now.diff(birthDate.add(diff, 'year'), 'month');
  const days = now.diff(birthDate.add(diff, 'year').add(months, 'month'), 'day');

  return { years: diff, months, days };
}

export default function App() {
  const [birthDate, setBirthDate] = useState(null);
  const [age, setAge] = useState(null);
  const [error, setError] = useState('');

  const handleCalculate = () => {
    if (!birthDate) {
      setError('Please select a valid birth date.');
      setAge(null);
      return;
    }

    const selected = dayjs(birthDate);
    if (selected.isAfter(dayjs())) {
      setError('Birth date cannot be in the future.');
      setAge(null);
      return;
    }

    setError('');
    setAge(calculateAge(selected));
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper elevation={3} sx={{ p: 4, borderRadius: 2 }}>
        <Typography variant="h4" align="center" gutterBottom>
          Age Calculator
        </Typography>

        <Box sx={{ my: 3 }}>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <DatePicker
              label="Select your birth date"
              value={birthDate}
              onChange={(newValue) => setBirthDate(newValue)}
              renderInput={(params) => (
                <TextField fullWidth {...params} />
              )}
            />
          </LocalizationProvider>
        </Box>

        {error && (
          <Typography color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        <Button
          variant="contained"
          color="primary"
          fullWidth
          onClick={handleCalculate}
        >
          Calculate Age
        </Button>

        {age && (
          <Card sx={{ mt: 4, backgroundColor: '#e3f2fd' }}>
            <CardContent>
              <Typography variant="h6" align="center" gutterBottom>
                Your Age
              </Typography>
              <Grid container spacing={2} justifyContent="center">
                <Grid item>
                  <Typography variant="subtitle1">
                    <strong>{age.years}</strong> years
                  </Typography>
                </Grid>
                <Grid item>
                  <Typography variant="subtitle1">
                    <strong>{age.months}</strong> months
                  </Typography>
                </Grid>
                <Grid item>
                  <Typography variant="subtitle1">
                    <strong>{age.days}</strong> days
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        )}
      </Paper>
    </Container>
  );
}