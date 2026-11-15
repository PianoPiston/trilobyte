# Security response

Security incidents are owned by the Orders AI on-call engineer. Middleware is not considered the only authorization layer in a production deployment. During an applicable middleware advisory, add defense-in-depth authorization checks in the affected route handlers, upgrade to the advisory's fixed version, and run the application-owned security suite before closing the incident.
