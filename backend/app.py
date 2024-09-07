from flask import Flask, redirect, request, jsonify, session, send_from_directory
import requests, os, datetime, urllib.parse, json
from datetime import datetime
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import asc
from db_operations import Track, Recommendations, TruePlaylist, FalsePlaylist, EndpointRequest, Search, engine

#TODO: fix duplicate playlist

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173"] ,supports_credentials=True)
app.secret_key = os.urandom(24)
load_dotenv()

Session = sessionmaker(bind=engine)
DBsession = Session()

dist_folder = os.path.join(os.getcwd(),"..","frontend","dist")
@app.route("/",defaults={"filename":""})
@app.route("/<path:filename>")
def index(filename):
    if not filename:
        filename = "index.html"
    return send_from_directory(dist_folder,filename)

@app.route('/refresh-token')
def refresh_access_token():
    if 'refresh_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': os.getenv("CLIENT_ID"),
            'client_secret': os.getenv("CLIENT_SECRET")
        }

    response = requests.post(os.getenv("TOKEN_URL"), data=req_body)

    if response.status_code == 200:
        new_token_info = response.json()
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']
        
        return redirect(os.getenv("HOME_URL"))

@app.route('/login')
def login():
    scope = 'user-read-private, user-read-email, user-library-read, playlist-read-private, playlist-read-collaborative, playlist-modify-public, playlist-modify-private'
    params = {
        'client_id': os.getenv("CLIENT_ID"),
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': os.getenv("REDIRECT_URI"),
        'show_dialog': False,  # True forces relogin for debugging
    }

    auth_url = f"{os.getenv('AUTH_URL')}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url) #do not change url

@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    if 'code' in request.args:
        req_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': os.getenv("REDIRECT_URI"),
            'client_id': os.getenv("CLIENT_ID"),
            'client_secret': os.getenv("CLIENT_SECRET")
        }

        response = requests.post(os.getenv("TOKEN_URL"), data=req_body)
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to get access token"}), response.status_code
        
        token_info = response.json()
        
        session['access_token'] = token_info.get('access_token')
        session['refresh_token'] = token_info.get('refresh_token')
        session['expires_at'] = datetime.now().timestamp() + token_info.get('expires_in', 3600)

        return redirect(os.getenv("HOME_URL"))

def tokencheck():
    if 'access_token' not in session:
        return redirect('/login')
    
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('refresh-token')

##--POST LOGIN FUNCTIONS UNDERNEATH--##

@app.route('/api/search', methods=['POST','GET'])
def search():
    tokencheck()
    DBsession.query(Search).delete()
    DBsession.commit()
    data = request.get_json()
    query_text = data.get('query')

    params = {
        'q': query_text,
        'type': ['track', 'artist'],
        'limit': 1,
        'offset': 0
    }

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    response = requests.get('https://api.spotify.com/v1/search', params=params, headers=headers)
    response.raise_for_status()  # Raise HTTPError for bad responses
    
    search_json = response.json()
    for track in search_json["tracks"]["items"]:
        track_id = track["id"]
        searched_track = Search(id=track_id)
        DBsession.add(searched_track)
        DBsession.commit()
    return jsonify({'track_id': track_id})

@app.route('/api/playlists')
def get_playlists():
    tokencheck()
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    } 
    response = requests.get(os.getenv("API_BASE_URL") + 'me/playlists', headers=headers)
    return(response.json())

@app.route('/api/user')
def get_spotify_user():
    tokencheck()
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    response = requests.get(os.getenv("API_BASE_URL") + 'me', headers=headers)
    return response.json()
#each of their song radios will be added to the database at varying limits (song amounts)

@app.route('/api/tracks')
def get_liked_tracks():
    tokencheck()

    #endpoint to get users liked songs
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    response = requests.get(os.getenv("API_BASE_URL") + 'me/tracks?limit=10', headers=headers)
   
    try:
        track_json = response.json()
        for item in track_json["items"]:
            track = item["track"]
            track_id = track["id"]
            track_name = track["name"]
            existing_track = DBsession.query(Track).filter(Track.id == track_id).first()
            if existing_track:
                existing_track.name = track_name
            else:
                liked_tracks = Track(id=track_id, name=track_name)
                DBsession.add(liked_tracks)
            
            DBsession.commit()
    except Exception as e:
        DBsession.rollback()
        return {"error in database for liked": str(e)}, 500
    finally:
        DBsession.close()
    return response.json()

## below is functionality for creating a palylist based on a single songs recommendations that are in the liked playlist ##
@app.route('/api/refresh-liked-database')
def refresh_liked_database():
    DBsession.query(TruePlaylist).delete()
    DBsession.query(EndpointRequest).delete()
    DBsession.commit()
    return redirect(('/api/get-liked-recommendations'))

@app.route('/api/refresh-unliked-database')
def refresh_false_database():
    DBsession.query(FalsePlaylist).delete()
    DBsession.query(EndpointRequest).delete()
    DBsession.commit()
    return redirect(('/api/get-unliked-recommendations'))

@app.route('/api/get-liked-recommendations')
def get_liked_recommendations():
    recommendations()
    return(redirect('/api/get-liked'))

@app.route('/api/get-unliked-recommendations')
def get_unliked_recommendations():
    recommendations()
    return(redirect('/api/get-unliked'))

def recommendations():
    tokencheck()
    #endpoint to get track recommendations songs
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    #delete any recommendations from prior request
    DBsession.query(Recommendations).delete()
    DBsession.commit()
    latest_search = DBsession.query(Search.id).first()

    if latest_search:
        seed_track_id = latest_search[0]
    else:
        return {'error': 'No search found'}, 400

    try:
        response = requests.get(os.getenv("API_BASE_URL")+f'recommendations?limit=50&seed_tracks={seed_track_id}', headers=headers)
        recommendations_json = response.json()
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            print("Too Many Requests: Retry after", retry_after, "seconds.")
        elif response.status_code == 401:
            print("Unauthorized: Check your access token.")
        elif response.status_code == 400:
            print("Bad Request: Check your query parameters.")
        else:
            print(f"HTTP error occurred: {http_err}")
        return {'error': {'status': response.status_code, 'message': response.text}}, response.status_code
    except Exception as err:
        print(f"Other error occurred: {err}")
        return {'error': {'status': 500, 'message': 'Internal server error.'}}, 500

    i = 1
    try:
        for track in recommendations_json["tracks"]:
            track_id = track["id"]
            track_name = track["name"]
            existing_track = DBsession.query(Track).filter(Recommendations.id == track_id).first()
            if existing_track:
                existing_track.name = track_name
            else:
                track_recommendations = Recommendations(index= i, id=track_id, name=track_name)
                DBsession.add(track_recommendations)
                i = i + 1

            DBsession.commit()
    except Exception as e:
        DBsession.rollback()
        return {"error database in /recommendations": str(e)}, 500
    finally:
        DBsession.close()
        return None
#this database matches spotify response json

@app.route('/api/get-liked')
def get_liked():
    tokencheck()
    headers = {
    'Authorization': f"Bearer {session['access_token']}"
    }
    request_counter = DBsession.query(EndpointRequest).count()
    while request_counter <= 5:
        print ("request counter: ", request_counter)

        #query and save the recommendations table
        recommendations_id = DBsession.query(Recommendations.id).order_by(asc(Recommendations.index)).limit(100).all()
        recommendations_name = DBsession.query(Recommendations.name).order_by(asc(Recommendations.index)).limit(100).all()
        track_id_list = [str(recommendation.id) for recommendation in recommendations_id]
        track_id_join = ','.join(track_id_list)
        
        #get the saved/liked tracks playlist
        response = requests.get(os.getenv("API_BASE_URL") + 'me/tracks/contains?ids='+track_id_join, headers=headers)
        liked_tracks_json = response.json()
        print(liked_tracks_json)
        #index the 'true' bool from the json data
        liked_track_string = json.dumps(liked_tracks_json)
        split_string = liked_track_string.split()
        true_index=[]

        for i, string in enumerate(split_string):
            if 'true' in string:
                true_index.append(i+1)

        if true_index == []:
            #all recommendations returned false for liked
            print("No liked songs in recommendations pull")
        new_name_list = [str(recommendation.name) for recommendation in recommendations_name]
        for j, track in enumerate(track_id_list):
            if j in true_index and j<100:
                existing_track = DBsession.query(TruePlaylist).filter(TruePlaylist.id == track_id_list[j-1]).first()
                if existing_track:
                    existing_track.name = new_name_list[j-1]
                else:
                    true_tracks = TruePlaylist(id=track_id_list[j-1], name=new_name_list[j-1])
                    DBsession.add(true_tracks)
            DBsession.commit()
        request_counter = request_counter + 1
        index_counter = EndpointRequest(index=request_counter)
        DBsession.add(index_counter)
        DBsession.commit()
        return redirect('/api/get-liked-recommendations')
    return redirect('/api/create-liked-playlist')

@app.route('/api/get-unliked')
def get_false():
    tokencheck()
    headers = {
    'Authorization': f"Bearer {session['access_token']}"
    }
    request_counter = DBsession.query(EndpointRequest).count()
    while request_counter <= 2:
        print ("request counter: ", request_counter)

        #query and save the recommendations table
        recommendations_id = DBsession.query(Recommendations.id).order_by(asc(Recommendations.index)).limit(100).all()
        recommendations_name = DBsession.query(Recommendations.name).order_by(asc(Recommendations.index)).limit(100).all()
        track_id_list = [str(recommendation.id) for recommendation in recommendations_id]
        track_id_join = ','.join(track_id_list)
        
        #get the saved/liked tracks playlist
        response = requests.get(os.getenv("API_BASE_URL") + 'me/tracks/contains?ids='+track_id_join, headers=headers)
        liked_tracks_json = response.json()
        print(liked_tracks_json)
        #index the 'true' bool from the json data
        liked_track_string = json.dumps(liked_tracks_json)
        split_string = liked_track_string.split()
        false_index=[]

        for i, string in enumerate(split_string):
            if 'false' in string:
                false_index.append(i+1)

        if false_index == []:
            #all recommendations returned false for liked
            print("No liked songs in recommendations pull")

        #find the corresponding indeces in the recommendations data
        new_name_list = [str(recommendation.name) for recommendation in recommendations_name]
        for j, track in enumerate(track_id_list):
            if j in false_index and j<100:
                existing_track = DBsession.query(FalsePlaylist).filter(FalsePlaylist.id == track_id_list[j-1]).first()
                if existing_track:
                    existing_track.name = new_name_list[j-1]
                else:
                    false_tracks = FalsePlaylist(id=track_id_list[j-1], name=new_name_list[j-1])
                    DBsession.add(false_tracks)
            DBsession.commit()

        request_counter = request_counter + 1
        index_counter = EndpointRequest(index=request_counter)
        DBsession.add(index_counter)
        DBsession.commit()
        return redirect('/api/get-unliked-recommendations')
    return redirect('/api/create-unliked-playlist')

@app.route('/api/create-liked-playlist')
def create_liked_playlist():
    tokencheck()
    headers = {
    'Authorization': f"Bearer {session['access_token']}"
    }
    #get searched song
    searched_track = DBsession.query(Search.id).first()
    searched_str = searched_track[0]
    searched_str = str(searched_str)

    track_response = requests.get(os.getenv("API_BASE_URL") + f'tracks/{searched_track.id}', headers=headers)
    track_data = track_response.json()
    track_name = track_data.get("name")
    #get user id for creating playlist
    user_response = requests.get(os.getenv("API_BASE_URL") + 'me', headers=headers)
    user_json = user_response.json()
    user_id = None
    user_id = user_json.get('id')

    #LIKED PLAYLIST
    #create playlist and get playlist id
    liked_playlist_body = f'{{ "name": "Favourited tracks Radio", "description": "Based on: {track_name}, automated from website: spotifyradiosort.onrender.com", "public": false }}'
    liked_playlist_response = requests.post(os.getenv("API_BASE_URL") + 'users/'+user_id+'/playlists', data=liked_playlist_body, headers=headers)
    liked_playlist_json = liked_playlist_response.json()
    liked_playlist_id = liked_playlist_json.get('id')

    #get track id from databse and insert uri
    liked_tracks_id = DBsession.query(TruePlaylist.id).limit(11).all()
    liked_track_id_list = [str(track.id) for track in liked_tracks_id]
    liked_track_id_list.insert(0,searched_str)
    prefix = 'spotify:track:'
    liked_track_id_list = [prefix + item for item in liked_track_id_list]   

    liked_add_tracks_body = json.dumps({ "uris": liked_track_id_list })
    liked_response = requests.post(os.getenv("API_BASE_URL") + 'playlists/'+liked_playlist_id+'/tracks', data=liked_add_tracks_body, headers=headers)

    playlist_ids = [liked_playlist_id] 
    return jsonify(playlist_ids)

@app.route('/api/create-unliked-playlist')
def create_unliked_playlist():
    tokencheck()
    headers = {
    'Authorization': f"Bearer {session['access_token']}"
    }
    searched_track = DBsession.query(Search.id).first()
    searched_str = searched_track[0]
    searched_str = str(searched_str)

    track_response = requests.get(os.getenv("API_BASE_URL") + f'tracks/{searched_track.id}', headers=headers)
    track_data = track_response.json()
    track_name = track_data.get("name")
    #get user id for creating playlist
    user_response = requests.get(os.getenv("API_BASE_URL") + 'me', headers=headers)
    user_json = user_response.json()
    user_id = None
    user_id = user_json.get('id')
   #NEW PLAYLIST
    new_playlist_body = f'{{ "name": "New tracks Radio", "description": "Based on: {track_name}. Automated from website", "public": false }}'
    new_playlist_response = requests.post(os.getenv("API_BASE_URL") + 'users/'+user_id+'/playlists', data=new_playlist_body, headers=headers)
    new_playlist_json = new_playlist_response.json()
    new_playlist_id = new_playlist_json.get('id')

    #get track id from databse and insert uri
    new_tracks_id = DBsession.query(FalsePlaylist.id).limit(11).all()
    new_track_id_list = [str(track.id) for track in new_tracks_id]
    new_track_id_list.insert(0,searched_str)
    prefix = 'spotify:track:'
    new_track_id_list = [prefix + item for item in new_track_id_list]   

    add_tracks_body = json.dumps({ "uris": new_track_id_list })
    new_response = requests.post(os.getenv("API_BASE_URL") + 'playlists/'+new_playlist_id+'/tracks', data=add_tracks_body, headers=headers)

    playlist_ids = [new_playlist_id] 
    return jsonify(playlist_ids)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
