# Tournament Tracker

## Overview

Tournament Tracker is a sophisticated web application designed to manage and track sports tournaments. It provides a comprehensive solution for tournament organizers, participants, and spectators to create, manage, and follow tournament brackets, place bets, and view live updates of matches.

## Features

1. **Tournament Management**
   - Create new tournaments
   - Edit existing tournaments
   - Archive or delete tournaments
   - Set tournaments as active or inactive

2. **Team and Player Management**
   - Add teams to tournaments
   - Add players to teams
   - View team and player details

3. **Bracket Generation**
   - Automatically generate tournament brackets
   - Support for various tournament sizes
   - Dynamic bracket updates as matches progress

4. **Match Management**
   - Update match scores in real-time
   - Set match winners
   - Automatically advance winners to the next round

5. **Betting System**
   - Allow users to place bets on teams
   - Calculate and display odds for each team
   - Track bets and potential payouts

6. **Admin Dashboard**
   - Comprehensive admin interface for tournament management
   - Real-time bracket editing and match updates
   - User-friendly forms for adding teams and players

7. **Public Tournament View**
   - Display active tournament brackets
   - Show live match updates
   - Present current betting odds

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, JavaScript, Tailwind CSS
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migration Tool**: Alembic
- **Containerization**: Docker and Docker Compose

## Project Structure

## Technical Details

### Database Schema

The application uses PostgreSQL with SQLAlchemy ORM. The main models are:

1. **Tournament**: Represents a tournament with fields for name, description, active status, and archived status.
2. **Team**: Represents a team participating in a tournament.
3. **Player**: Represents a player belonging to a team.
4. **Bet**: Represents a bet placed on a team in a tournament.
5. **Round**: Represents a round in a tournament bracket.
6. **Match**: Represents a match between two teams in a tournament round.

### API Reference

#### Public Endpoints

1. **GET /** 
   - Description: Main page displaying the active tournament
   - Response: HTML page

2. **GET /tournament/{tournament_id}/bracket**
   - Description: Get the bracket for a specific tournament
   - Parameters: 
     - tournament_id (int): ID of the tournament
   - Response: JSON object containing bracket information

3. **GET /odds/{tournament_id}**
   - Description: Get the current odds for a tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Response: JSON object with team names and their odds

4. **POST /place_bet/{match_id}/{team_id}**
   - Description: Place a bet on a team for a specific match
   - Parameters:
     - match_id (int): ID of the match
     - team_id (int): ID of the team
   - Request Body:
     - amount (float): Bet amount
     - full_name (string): Name of the bettor
   - Response: JSON object with success message or error details

5. **GET /match/{match_id}**
   - Description: Get details for a specific match
   - Parameters:
     - match_id (int): ID of the match
   - Response: JSON object with match details

#### Admin Endpoints

1. **GET /admin**
   - Description: Admin dashboard
   - Response: HTML page

2. **POST /admin/create_tournament**
   - Description: Create a new tournament
   - Request Body:
     - name (string): Tournament name
     - description (string): Tournament description
   - Response: Redirect to admin dashboard

3. **POST /admin/edit_tournament/{tournament_id}**
   - Description: Edit an existing tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Request Body:
     - name (string): Updated tournament name
     - description (string): Updated tournament description
     - is_active (boolean): Tournament active status
   - Response: Redirect to admin dashboard

4. **POST /admin/add_team/{tournament_id}**
   - Description: Add a team to a tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Request Body:
     - team_name (string): Name of the new team
     - player_names (list of strings): Names of players in the team
   - Response: Redirect to admin dashboard

5. **POST /admin/generate_bracket/{tournament_id}**
   - Description: Generate the bracket for a tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Response: JSON object with success message or error details

6. **POST /admin/update_match/{match_id}**
   - Description: Update match details (scores, winner)
   - Parameters:
     - match_id (int): ID of the match
   - Request Body:
     - winner_name (string): Name of the winning team
     - team1_score (int): Score of team 1
     - team2_score (int): Score of team 2
   - Response: JSON object with success message or error details

7. **POST /admin/delete_tournament/{tournament_id}**
   - Description: Delete a tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Response: JSON object with success message or error details

8. **POST /admin/archive_tournament/{tournament_id}**
   - Description: Archive a tournament
   - Parameters:
     - tournament_id (int): ID of the tournament
   - Response: JSON object with success message or error details

### Key Technical Components

1. **Bracket Generation**: 
   The system uses a mathematical approach to determine the number of rounds based on the number of teams. It creates a balanced bracket structure, handling cases where the number of teams is not a power of 2.

2. **Real-time Updates**:
   The frontend uses JavaScript to periodically fetch updated bracket and odds information from the server, providing a near-real-time experience for users without requiring a full page reload.

3. **Betting System**:
   The application calculates odds based on the total amount bet on each team and the overall bet pool for the tournament. This is updated in real-time as new bets are placed.

4. **Match Progression**:
   As match results are updated, the system automatically advances winners to the next round in the bracket, updating the tournament structure dynamically.

5. **Database Migrations**:
   The project uses Alembic for database migrations, allowing for easy schema updates and version control of the database structure.

6. **Containerization**:
   Docker and Docker Compose are used to containerize the application, ensuring consistency across different development and deployment environments.

## Setup and Installation

## Contributing

## License
