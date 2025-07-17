import React, { useState, useEffect } from 'react';
import Button from './components/Button/Button';
import './App.css';

function App() {
  const [recordings, setRecordings] = useState([]);
  const [selectedRecording, setSelectedRecording] = useState(null);

  useEffect(() => {
    fetch('/recordings')
      .then(response => response.json())
      .then(data => setRecordings(data));
  }, []);

  const handleRecordingClick = (recording) => {
    setSelectedRecording(recording);
  };

  return (
    <div className="App">
      <div className="sidebar">
        <h2>Recordings</h2>
        <ul>
          {recordings.map(recording => (
            <li key={recording.id} onClick={() => handleRecordingClick(recording)}>
              {recording.title}
            </li>
          ))}
        </ul>
      </div>
      <div className="main-content">
        {selectedRecording ? (
          <div>
            <h3>{selectedRecording.title}</h3>
            <p>{selectedRecording.transcription}</p>
            <Button>Edit</Button>
          </div>
        ) : (
          <p>Select a recording to view details.</p>
        )}
      </div>
    </div>
  );
}

export default App;
