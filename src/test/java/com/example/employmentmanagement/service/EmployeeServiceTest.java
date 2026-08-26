package com.example.employmentmanagement.service;

import com.example.employmentmanagement.exception.DuplicateEmailException;
import com.example.employmentmanagement.exception.EmployeeNotFoundException;
import com.example.employmentmanagement.model.Employee;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EmployeeServiceTest {

    private EmployeeService employeeService;

    @BeforeEach
    void setUp() {
        employeeService = new EmployeeService();
    }

    @Test
    void createEmployeeAssignsSequentialId() {
        Employee created = employeeService.createEmployee(sample("Manjunath", "manjunath@example.com"));
        assertEquals(1L, created.getId());
        assertEquals("Manjunath", created.getName());
        assertEquals("Software Engineer", created.getOccupation());
        assertEquals("manjunath@example.com", created.getEmail());
        assertEquals(5, created.getYearsOfExperience());
    }

    @Test
    void createMultipleEmployeesKeepsUniqueIdsAndAllRecords() {
        for (int i = 1; i <= 10; i++) {
            employeeService.createEmployee(sample("Employee " + i, "employee" + i + "@example.com"));
        }

        List<Employee> all = employeeService.getAllEmployees();
        assertEquals(10, all.size());
        for (int i = 0; i < 10; i++) {
            assertEquals((long) (i + 1), all.get(i).getId());
            assertEquals("Employee " + (i + 1), all.get(i).getName());
        }
    }

    @Test
    void getAllEmployeesReturnsEmptyListWhenNoneExist() {
        assertTrue(employeeService.getAllEmployees().isEmpty());
    }

    @Test
    void getEmployeeByIdReturnsExistingEmployee() {
        Employee created = employeeService.createEmployee(sample("Priya", "priya@example.com"));
        Employee found = employeeService.getEmployeeById(created.getId());
        assertEquals("Priya", found.getName());
    }

    @Test
    void getEmployeeByIdThrowsWhenMissing() {
        EmployeeNotFoundException ex = assertThrows(
                EmployeeNotFoundException.class,
                () -> employeeService.getEmployeeById(10L));
        assertEquals("Employee with ID 10 not found", ex.getMessage());
    }

    @Test
    void updateEmployeeKeepsSameId() {
        Employee created = employeeService.createEmployee(sample("Manjunath", "manjunath@example.com"));
        Employee update = sample("Manjunath Updated", "manjunath.updated@example.com");
        update.setOccupation("Senior Software Engineer");
        update.setYearsOfExperience(6);

        Employee updated = employeeService.updateEmployee(created.getId(), update);

        assertEquals(created.getId(), updated.getId());
        assertEquals("Manjunath Updated", updated.getName());
        assertEquals("Senior Software Engineer", updated.getOccupation());
        assertEquals(6, updated.getYearsOfExperience());
        assertEquals(1, employeeService.getAllEmployees().size());
    }

    @Test
    void updateNonexistentEmployeeThrows() {
        assertThrows(EmployeeNotFoundException.class,
                () -> employeeService.updateEmployee(99L, sample("Missing", "missing@example.com")));
    }

    @Test
    void deleteEmployeeRemovesOnlyRequestedRecord() {
        employeeService.createEmployee(sample("One", "one@example.com"));
        Employee two = employeeService.createEmployee(sample("Two", "two@example.com"));
        employeeService.createEmployee(sample("Three", "three@example.com"));

        employeeService.deleteEmployee(two.getId());

        List<Employee> remaining = employeeService.getAllEmployees();
        assertEquals(2, remaining.size());
        assertEquals("One", remaining.get(0).getName());
        assertEquals("Three", remaining.get(1).getName());
    }

    @Test
    void deleteNonexistentEmployeeThrows() {
        assertThrows(EmployeeNotFoundException.class, () -> employeeService.deleteEmployee(2L));
    }

    @Test
    void duplicateEmailIsRejectedOnCreate() {
        employeeService.createEmployee(sample("First", "shared@example.com"));
        assertThrows(DuplicateEmailException.class,
                () -> employeeService.createEmployee(sample("Second", "shared@example.com")));
        assertEquals(1, employeeService.getAllEmployees().size());
    }

    @Test
    void duplicateEmailIsRejectedOnUpdate() {
        employeeService.createEmployee(sample("First", "first@example.com"));
        Employee second = employeeService.createEmployee(sample("Second", "second@example.com"));
        Employee update = sample("Second", "first@example.com");
        assertThrows(DuplicateEmailException.class, () -> employeeService.updateEmployee(second.getId(), update));
    }

    @Test
    void employeeMayKeepOwnEmailOnUpdate() {
        Employee created = employeeService.createEmployee(sample("First", "first@example.com"));
        Employee updated = employeeService.updateEmployee(created.getId(), sample("First Updated", "first@example.com"));
        assertEquals("First Updated", updated.getName());
        assertEquals("first@example.com", updated.getEmail());
    }

    private Employee sample(String name, String email) {
        return new Employee(null, name, "Software Engineer", email, 5);
    }
}
