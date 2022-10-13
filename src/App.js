import * as React from 'react';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Autocomplete from '@mui/material/Autocomplete';
import Stack from '@mui/material/Stack';
import dayjs, { Dayjs } from 'dayjs';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import FormLabel from '@mui/material/FormLabel';
import FormControl from '@mui/material/FormControl';
import FormGroup from '@mui/material/FormGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Checkbox from '@mui/material/Checkbox';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';



function App() {
  // const [value, setValue] = React.useState < Dayjs | null > (dayjs('2022-04-07'));
  const [state, setState] = React.useState({
    bunker: true,
    sandeels: false,
    rainfish: false,
  });

  const handleChange = (event) => {
    setState({
      ...state,
      [event.target.name]: event.target.checked,
    });
  };

  const { bunker, sandeels, rainfish } = state;
  const error = [bunker, sandeels, rainfish].filter((v) => v).length !== 2;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <Stack spacing={1} sx={{ width: 300 }}>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DateTimePicker
            label="Start Time"
            renderInput={(params) => <TextField {...params} />}
          // value={value}
          // onChange={(newValue) => {
          //   setValue(newValue);
          // }}
          />
          <DateTimePicker
            label="End Time"
            renderInput={(params) => <TextField {...params} />}
          // value={value}
          // onChange={(newValue) => {
          //   setValue(newValue);
          // }}
          />
        </LocalizationProvider>,
        <FormControl>
          <FormLabel id="approach">Approach</FormLabel>
          <RadioGroup
            row
            aria-labelledby="approach"
            name="row-radio-buttons-group"
          >
            <FormControlLabel value="surf" control={<Radio />} label="surf" />
            <FormControlLabel value="boat" control={<Radio />} label="boat" />
          </RadioGroup>
        </FormControl>,
        <FormControl sx={{ m: 3 }} component="fieldset" variant="standard">
          <FormLabel component="legend">Bait Present</FormLabel>
          <FormGroup>
            <FormControlLabel
              control={
                <Checkbox checked={bunker} onChange={handleChange} name="bunker" />
              }
              label="bunker"
            />
            <FormControlLabel
              control={
                <Checkbox checked={sandeels} onChange={handleChange} name="sandeels" />
              }
              label="sandeels"
            />
            <FormControlLabel
              control={
                <Checkbox checked={rainfish} onChange={handleChange} name="rainfish" />
              }
              label="rainfish"
            />
          </FormGroup>
          {/* <FormHelperText>Be careful</FormHelperText> */}
        </FormControl>,
        <Typography id="quantity" gutterBottom>
        Quantity Caught
        </Typography>,
        <Slider
          aria-label="Quantity Caught"
          defaultValue={0}
          step={1}
          max={20}
          valueLabelDisplay="on"
        />,
        <Button variant='contained' color='primary'>Submit</Button>
      </Stack>
    </div>
  )
}

export default App;
