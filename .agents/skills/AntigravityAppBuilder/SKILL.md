---
name: AntigravityAppBuilder
description: Compiles a raw hackathon spec into a production-ready application using strict SDLC phases.
---

# Antigravity App Builder Skill

This skill is designed as an agentic pipeline that ingests a raw/chaotic hackathon spec list and processes it through a rigorous, step-by-step **Software Development Lifecycle (SDLC)** before generating code.

## Execution Protocol

Follow the SDLC phases sequentially. Each phase requires explicit validation or completion before moving to the next.

### Phase 1: Product Requirement Document (PRD)
- **Goal**: Analyze the user's specification list, separating noise from signal.
- **Action**: Write a lean and mean PRD focusing heavily on the MVP scope.
- **Key Components**:
  - **The "Why"**: The core problem statement and value proposition.
  - **User Personas & User Stories**: *"As a user, I want to [action] so that [benefit]."*
  - **MVP Scope Definition**: A strict categorization of features into **Must-Have** (for the pitch), **Should-Have**, and **Could-Have** (Nice-to-have).
  - **Success Metrics**: What defines a working demo by the end of the hackathon?
- **Gatekeeper**: **STOP and wait for user approval/refinement** on the PRD before moving to Phase 2.

### Phase 2: System Architecture & Tech Stack Selection
- **Goal**: Establish the system skeleton, data flow, and where things live.
- **Action**: Design a high-level conceptual architecture and select an optimal, rapid-development tech stack. Define service boundaries.
- **Key Components**:
  - **System Diagram (Conceptual)**: Defining Client-Server relationships (e.g., Next.js frontend communicating with a FastAPI backend).
  - **Tech Stack Justification**: Choosing tools optimized for speed of development and reliability (e.g., Supabase for instant Auth/DB, Vercel for deployment).
  - **Third-Party Integrations**: Identifying APIs, LLMs, or auth providers needed.
- **Gatekeeper**: **STOP and wait for user approval** before moving to Phase 3.

### Phase 3: Data Modeling & API Design (Contracts)
- **Goal**: Structure database logic and API contracts so frontend/backend development can happen in parallel.
- **Action**: Generate a database schema (relational/non-relational) and map out explicit API contracts (JSON requests/responses).
- **Key Components**:
  - **Data Schema (ERD)**: Table names, primary keys, foreign keys, data types, and relationships.
  - **API Contract/Specification**: Endpoints, request body payloads, response status codes, and response structures.
- **Gatekeeper**: **STOP and wait for user approval** before moving to Phase 4.

### Phase 4: Implementation Roadmap & Code Generation
- **Goal**: Build and integrate the application based on the approved specifications.
- **Action**: Execute code generation sequentially. Do not hallucinate dependencies.
- **Execution Order**:
  - 1. **Environment Setup**: Configuration files (`.env.example`, `package.json`, `Dockerfile`, etc.).
  - 2. **Database Migration**: Scripts to spin up the schema.
  - 3. **Backend Core**: Route handlers, controllers, and business logic.
  - 4. **Frontend Shell**: Component hierarchy, state management, and routing.
  - 5. **Integration**: Hooking the frontend UI up to the API endpoints.
