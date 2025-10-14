### Project Roadmap: Version 1.0

This roadmap outlines the development plan for the initial version of the application Checkboxes can be used to track progress.

### Phase 1: Project Setup
- [✔️] Initialize the project directory structure
- [] Create a `Dockerfile` for the python backend service
- [] Create a `docker-compose.yml` file to manage the backend and database services
- [] Configure basic Docker networking and volumes for database persistence

### Phase 2: Database & Models
- [] Design and implement the `Transaction` table schema using SQLAlchemy ORM
- [] Establish a database connection handler that reads credentials from environment variables
- [] Implement logic to create initial database tables on startup

### Phase 3: Basic API
- [] Develop a `POST /transaction` endpoint to recieve new transaction data
- [] Implement the core rule-based fraud detection logic
- [] Develop a `GET /transaction` endpoint to retrieve all processed transactions
- [] Add a `GET /health` endpoint for health checks

### Phase 4: Frontend 
- [] Create an `index.html file with a form to submit transaction details
- [] Write `app.js` to handle form submission using the `fetch()` API to call the backend
- [] Display the fraud analysis result and transaction history on the webpage
- [] Apply basic styling with `styles.css`

### Phase 5: Testing & Polishing
- [] Write unit tests for the rule-based logic using `pytest`
- [] Write basic integration tests for the API endpoints
- [] Add comments to the code for clarity
- [] Finalize and update this README with complete setup and usage instructions