import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './SpotifyData.css'; // Import your CSS file here

const SpotifyData = ({ userData }) => {
    const [playlistData, setPlaylistData] = useState([]);
    const [query, setQuery] = useState('');
    const [results, setResults] = useState('');
    const [loading, setLoading] = useState(false); // Loading state

    const sendData = async (url, data) => {
        try {
            const res = await axios.post(url, data, { withCredentials: true });
            console.log('Data sent successfully:', res.data);
            return res.data; 
        } catch (err) {
            console.error('Error sending data:', err);
        }
    };

    const handleSaveQuery = async (query) => {
        try {
            const response = await sendData('/api/search', { query });
            setResults(response.track_id); 
            console.log('Track ID:', response.track_id);
        } catch (err) {
            console.error('Error sending query:', err);
        }
    };

    const handleSearchChange = (e) => {
        setQuery(e.target.value);
    };

    const handleSearchSubmit = async (e) => {
        e.preventDefault();
        try {
            await handleSaveQuery(query);
        } catch (err) {
            console.error('Error sending query:', err);
        }
    };

    const handleGeneratePlaylists = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await axios.get('/api/refresh', { withCredentials: true });
            const res = await axios.get('/api/create-playlist', { withCredentials: true });
            console.log('Playlists generated:', res.data);
            setPlaylistData({
                liked_playlist_id: res.data[0],
                new_playlist_id: res.data[1],
            });
        } catch (err) {
            console.error('Error generating playlists:', err);
        } finally {
            setLoading(false); // Stop loading
        }
    };

    const trackLink = `https://open.spotify.com/embed/track/${results}?utm_source=generator`;
    
    const likedPlaylistLink = playlistData.liked_playlist_id 
        ? `https://open.spotify.com/embed/playlist/${playlistData.liked_playlist_id}?utm_source=generator`
        : '';
    const newPlaylistLink = playlistData.new_playlist_id 
        ? `https://open.spotify.com/embed/playlist/${playlistData.new_playlist_id}?utm_source=generator`
        : '';
        
    return (
        <div className="spotify-data">
            <form className="search-bar" onSubmit={handleSearchSubmit}>
                <input
                    type="text"
                    value={query}
                    onChange={handleSearchChange}
                    placeholder="Search for a track"
                />
                <button type="submit">Search</button>
            </form>
            {results && (
                    <div className="track-preview">
                        <iframe 
                            src={trackLink} 
                            width="100%" 
                            height="100" 
                            frameBorder="0" 
                            allowFullScreen="" 
                            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                            loading="lazy">
                        </iframe>
                    </div>           
                )}
            <div className="generate-playlist-container">
                <button type="button" onClick={handleGeneratePlaylists}>
                    Generate Playlists
                </button>
                <h4>Generated playlists will be automatically added to your Spotify</h4>
                {loading && <div className="loading-wheel"></div>}
            </div>
            <div className="playlists">
                <div className="playlist-container">
                    <h2>Liked Songs Only</h2>
                    <iframe 
                        src={likedPlaylistLink}
                        width="100%" 
                        height="352" 
                        frameBorder="0" 
                        allowFullScreen="" 
                        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                        loading="lazy">
                    </iframe>
                </div>
                <div className="playlist-container">
                    <h2>New Songs Only</h2>
                    <iframe 
                        src={newPlaylistLink}
                        width="100%" 
                        height="352" 
                        frameBorder="0" 
                        allowFullScreen="" 
                        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                        loading="lazy">
                    </iframe>
                </div>
            </div>
        </div>
    );
};

export default SpotifyData;
