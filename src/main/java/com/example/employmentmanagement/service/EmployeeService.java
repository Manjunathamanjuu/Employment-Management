package com.example.employmentmanagement.service;

import com.example.employmentmanagement.exception.DuplicateEmailException;
import com.example.employmentmanagement.exception.EmployeeNotFoundException;
import com.example.employmentmanagement.model.Employee;
import com.example.employmentmanagement.repository.EmployeeRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class EmployeeService {

    private static final Logger log = LoggerFactory.getLogger(EmployeeService.class);

    private final EmployeeRepository employeeRepository;

    public EmployeeService(EmployeeRepository employeeRepository) {
        this.employeeRepository = employeeRepository;
    }

    @Transactional
    public Employee createEmployee(Employee request) {
        String email = normalize(request.getEmail());
        ensureEmailAvailable(email, null);

        Employee employee = new Employee();
        employee.setName(normalize(request.getName()));
        employee.setOccupation(normalize(request.getOccupation()));
        employee.setEmail(email);
        employee.setYearsOfExperience(request.getYearsOfExperience());

        try {
            Employee saved = employeeRepository.save(employee);
            log.info("Created employee id={} email={}", saved.getId(), saved.getEmail());
            return saved;
        } catch (DataIntegrityViolationException ex) {
            log.warn("Create employee failed due to a constraint violation for email={}", email);
            throw new DuplicateEmailException();
        } catch (DataAccessException ex) {
            log.error("Create employee failed due to a database error");
            throw ex;
        }
    }

    @Transactional(readOnly = true)
    public List<Employee> getAllEmployees() {
        List<Employee> employees = employeeRepository.findAll(Sort.by(Sort.Direction.ASC, "id"));
        log.info("Retrieved {} employees from PostgreSQL", employees.size());
        return employees;
    }

    @Transactional(readOnly = true)
    public Employee getEmployeeById(Long id) {
        Employee employee = employeeRepository.findById(id)
                .orElseThrow(() -> new EmployeeNotFoundException(id));
        log.info("Retrieved employee id={}", id);
        return employee;
    }

    @Transactional
    public Employee updateEmployee(Long id, Employee request) {
        Employee existing = employeeRepository.findById(id)
                .orElseThrow(() -> new EmployeeNotFoundException(id));

        String email = normalize(request.getEmail());
        ensureEmailAvailable(email, id);

        existing.setName(normalize(request.getName()));
        existing.setOccupation(normalize(request.getOccupation()));
        existing.setEmail(email);
        existing.setYearsOfExperience(request.getYearsOfExperience());

        try {
            Employee saved = employeeRepository.save(existing);
            log.info("Updated employee id={} email={}", saved.getId(), saved.getEmail());
            return saved;
        } catch (DataIntegrityViolationException ex) {
            log.warn("Update employee id={} failed due to a constraint violation", id);
            throw new DuplicateEmailException();
        } catch (DataAccessException ex) {
            log.error("Update employee id={} failed due to a database error", id);
            throw ex;
        }
    }

    @Transactional
    public void deleteEmployee(Long id) {
        if (!employeeRepository.existsById(id)) {
            throw new EmployeeNotFoundException(id);
        }
        try {
            employeeRepository.deleteById(id);
            log.info("Deleted employee id={}", id);
        } catch (DataAccessException ex) {
            log.error("Delete employee id={} failed due to a database error", id);
            throw ex;
        }
    }

    private void ensureEmailAvailable(String email, Long currentId) {
        boolean taken = currentId == null
                ? employeeRepository.existsByEmailIgnoreCase(email)
                : employeeRepository.existsByEmailIgnoreCaseAndIdNot(email, currentId);
        if (taken) {
            log.info("Rejected duplicate email={}", email);
            throw new DuplicateEmailException();
        }
    }

    private String normalize(String value) {
        return value == null ? null : value.trim();
    }
}
