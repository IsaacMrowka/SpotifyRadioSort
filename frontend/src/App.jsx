import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import SpotifyData from './SpotifyData';
import axios from 'axios';
import './App.css';

const App = () => {
    const [userData, setUserData] = useState(null);
    const [showModal, setShowModal] = useState(false);

    useEffect(() => {
        const fetchUserData = async () => {
            try {
                const res = await axios.get('/api/user', { withCredentials: true });
                setUserData(res.data);
            } catch (err) {
                console.error('Error in acquiring user data', err);
            }
        };
        fetchUserData();
    }, []);

    const handleLogin = () => {
        window.location.href = 'http://localhost:5000/login';
    };

    const handleFeatureClick = () => {
        if (!userData) {
            setShowModal(true);
        }
    };

    const closeModal = () => {
        setShowModal(false);
    };

    return (
        <Router>
            <div className="app-container">
                <header className="header">
                    <h1 className="title">Spotify Radio Organizer</h1>
                    <div className="user-data">
                        {userData ? (
                            <div className="user-info">
                                <img src={userData.images[0].url} alt="User Profile" className="user-profile-image" />
                                <h2>{userData.display_name}</h2>
                            </div>
                        ) : (
                            <button className="login-button" onClick={handleLogin}>
                                Login with Spotify
                            </button>
                        )}
                    </div>
                </header>
                <main className="main-content" onClick={handleFeatureClick}>
                    <SpotifyData userData={userData} />
                </main>
                
                {showModal && (
                    <div className="modal-overlay" onClick={closeModal}>
                        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                            <h2>Login to continue :)</h2>
                            <button onClick={handleLogin} className="modal-login-button">Login with Spotify</button>
                            <button onClick={closeModal} className="modal-close-button">Close</button>
                        </div>
                    </div>
                )}
            </div>
        </Router>
    );
};

export default App;
