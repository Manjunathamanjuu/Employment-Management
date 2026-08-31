package com.example.employmentmanagement.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
public class DatabaseStartupLogger {

    private static final Logger log = LoggerFactory.getLogger(DatabaseStartupLogger.class);

    @Value("${POSTGRES_HOST:postgres}")
    private String host;

    @Value("${POSTGRES_PORT:5432}")
    private String port;

    @Value("${POSTGRES_DB:employee-managementdb}")
    private String database;

    @Value("${POSTGRES_USER:postgres}")
    private String user;

    @EventListener(ApplicationReadyEvent.class)
    public void logDatasourceConfiguration() {
        log.info(
                "PostgreSQL datasource configured: host={}, port={}, database={}, user={}",
                host,
                port,
                database,
                user);
        log.info("Application is using PostgreSQL as the source of truth for employees");
    }
}
