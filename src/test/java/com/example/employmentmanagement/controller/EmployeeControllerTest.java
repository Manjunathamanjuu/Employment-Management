package com.example.employmentmanagement.controller;

import com.example.employmentmanagement.PostgresIntegrationTest;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class EmployeeControllerTest extends PostgresIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void resetStore() {
        jdbcTemplate.execute("TRUNCATE TABLE employees RESTART IDENTITY");
    }

    @Test
    void postValidEmployeeReturns201() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Manjunath", "manjunath@example.com", 5)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(1))
                .andExpect(jsonPath("$.name").value("Manjunath"))
                .andExpect(jsonPath("$.email").value("manjunath@example.com"));
    }

    @Test
    void getAllReturns200AndEmptyArray() throws Exception {
        mockMvc.perform(get("/api/employees"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(0)));
    }

    @Test
    void getExistingEmployeeReturns200() throws Exception {
        mockMvc.perform(post("/api/employees")
                .contentType(MediaType.APPLICATION_JSON)
                .content(employeeJson("Asha", "asha@example.com", 3)));

        mockMvc.perform(get("/api/employees/1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Asha"));
    }

    @Test
    void getNonexistentEmployeeReturns404() throws Exception {
        mockMvc.perform(get("/api/employees/10"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Employee with ID 10 not found"));
    }

    @Test
    void putExistingEmployeeReturns200AndKeepsId() throws Exception {
        mockMvc.perform(post("/api/employees")
                .contentType(MediaType.APPLICATION_JSON)
                .content(employeeJson("Manjunath", "manjunath@example.com", 5)));

        mockMvc.perform(put("/api/employees/1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Manjunath Updated", "manjunath.updated@example.com", 6)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(1))
                .andExpect(jsonPath("$.name").value("Manjunath Updated"));
    }

    @Test
    void putNonexistentEmployeeReturns404() throws Exception {
        mockMvc.perform(put("/api/employees/1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Missing", "missing@example.com", 1)))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteExistingEmployeeReturns204() throws Exception {
        mockMvc.perform(post("/api/employees")
                .contentType(MediaType.APPLICATION_JSON)
                .content(employeeJson("Ravi", "ravi@example.com", 4)));

        mockMvc.perform(delete("/api/employees/1"))
                .andExpect(status().isNoContent());
    }

    @Test
    void deleteNonexistentEmployeeReturns404() throws Exception {
        mockMvc.perform(delete("/api/employees/2"))
                .andExpect(status().isNotFound());
    }

    @Test
    void invalidPostReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Validation failed"));
    }

    @Test
    void invalidEmailReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Test", "not-an-email", 2)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void negativeExperienceReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Test", "test@example.com", -1)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void invalidExperienceTypeReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "Test",
                                  "occupation": "Engineer",
                                  "email": "test@example.com",
                                  "yearsOfExperience": "five"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Invalid request body"));
    }

    @Test
    void invalidPutReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                .contentType(MediaType.APPLICATION_JSON)
                .content(employeeJson("Valid", "valid@example.com", 2)));

        mockMvc.perform(put("/api/employees/1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("  ", "still-valid@example.com", 2)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void duplicateEmailReturns400() throws Exception {
        mockMvc.perform(post("/api/employees")
                .contentType(MediaType.APPLICATION_JSON)
                .content(employeeJson("First", "shared@example.com", 1)));

        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Second", "shared@example.com", 2)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("An employee with this email already exists"));
    }

    @Test
    void invalidIdReturns400() throws Exception {
        mockMvc.perform(get("/api/employees/abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Invalid employee ID"));
    }

    @Test
    void multiplePostsAreAllReturned() throws Exception {
        for (int i = 1; i <= 10; i++) {
            mockMvc.perform(post("/api/employees")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(employeeJson("Employee " + i, "employee" + i + "@example.com", i)))
                    .andExpect(status().isCreated());
        }

        mockMvc.perform(get("/api/employees"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(10)))
                .andExpect(jsonPath("$[9].id").value(10));
    }

    @Test
    void createdEmployeeIsPersistedInPostgreSQL() throws Exception {
        mockMvc.perform(post("/api/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(employeeJson("Database Proof", "db.proof@example.com", 7)))
                .andExpect(status().isCreated());

        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM employees WHERE email = ?",
                Integer.class,
                "db.proof@example.com");
        org.junit.jupiter.api.Assertions.assertEquals(1, count);
    }

    private String employeeJson(String name, String email, int years) throws Exception {
        return objectMapper.writeValueAsString(Map.of(
                "name", name,
                "occupation", "Software Engineer",
                "email", email,
                "yearsOfExperience", years));
    }
}
