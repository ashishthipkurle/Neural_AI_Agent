import React, { useState } from "react";
import {
  Container,
  Box,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Stack,
} from "@mui/material";
import CalendarTodayIcon from "@mui/icons-material/CalendarToday";

function calculateAge(birthDate) {
  const today = new Date();
  const birth = new Date(birthDate);
  let years = today.getFullYear() - birth.getFullYear();
  let months = today.getMonth() - birth.getMonth();
  let days = today.getDate() - birth.getDate();

  if (days < 0) {
    months -= 1;
    days += new Date(today.getFullYear(), today.getMonth(), 0).getDate();
  }
  if (months < 0) {
    years -= 1;
    months += 12;
  }

  return { years, months, days };
}

export default function App() {
  const [dob, setDob] = useState("");
  const [age, setAge] = useState(null);
  const [error, setError] = useState("");

  const handleCalculate = () => {
    if (!dob) {
      setError("Please select a birth date.");
      setAge(null);
      return;
    }

    const birth = new Date(dob);
    const now = new Date();

    if (birth > now) {
      setError("Birth date cannot be in the future.");
      setAge(null);
      return;
    }

    setError("");
    setAge(calculateAge(dob));
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Card elevation={3}>
        <CardContent>
          <Stack spacing={3} alignItems="center">
            <Typography variant="h4" component="h1" gutterBottom>
              Age Calculator
            </Typography>

            <Box sx={{ display: "flex", alignItems: "flex-end", width: "100%" }}>
              <CalendarTodayIcon sx={{ color: "action.active", mr: 1, my: 0.5 }} />
              <TextField
                label="Birth Date"
                type="date"
                fullWidth
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                InputLabelProps={{ shrink: true }}
                error={!!error}
                helperText={error}
              />
            </Box>

            <Button variant="contained" size="large" onClick={handleCalculate}>
              Calculate Age
            </Button>

            {age && (
              <Box sx={{ mt: 2, textAlign: "center" }}>
                <Typography variant="h5">
                  You are{" "}
                  <strong>
                    {age.years} {age.years === 1 ? "year" : "years"},
                    {age.months} {age.months === 1 ? "month" : "months"} and{" "}
                    {age.days} {age.days === 1 ? "day" : "days"}
                  </strong>{" "}
                  old.
                </Typography>
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Container>
  );
}