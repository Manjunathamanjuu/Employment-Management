# Stage 1: Frontend — prepare static HTML/CSS/JavaScript assets
FROM alpine:3.20 AS frontend
WORKDIR /frontend
COPY src/main/resources/static/ ./static/

# Stage 2: Backend — compile the Spring Boot application with frontend assets
FROM maven:3.9-eclipse-temurin-21 AS backend
WORKDIR /app
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
COPY --from=frontend /frontend/static ./src/main/resources/static
RUN mvn -B -DskipTests package

# Stage 3: Runtime — lightweight JRE image with the application JAR only
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=backend /app/target/employment-management-1.0.0.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
