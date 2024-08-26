import React, {useState, useEffect} from 'react';
import {BrowserRouter as Router, Route, Routes} from 'react-router-dom';
import SpotifyData from './SpotifyData';
import axios from 'axios';
import './App.css';

const App = () => {
    const [userData, setUserData] = useState(null);

    useEffect(() => {
        const fetchUserData = async () => {
            try {
                const res = await axios.get('/api/user', { withCredentials: true });
                setUserData(res.data);
            }
            catch (err) { console.error('Error in aqcuiring user data', err)}
        }
        fetchUserData();
    }, []);

    const handleLogin = () => {
        window.location.href = 'https://spotifyradiosort.onrender.com/login';
    };

    return (
        <Router>
            <div>
                <header>
                <h1> Spotify Radio Organizer </h1>
                <h2>Playlists will be automatically saved to your library when generated</h2>
                    <div className="user-data">
                            {userData ? (
                                <div>
                                    <img src={userData.images[0].url}/>
                                    <h2>{userData.display_name}</h2>
                                </div>
                            ) : (
                                <button className="login-button" onClick={handleLogin}>Login with Spotify</button>
                            )}
                        </div>
                </header>
                <main>
                    <Routes>
                        <Route path="/" element={<SpotifyData userData={userData}/>} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
};

export default App;
