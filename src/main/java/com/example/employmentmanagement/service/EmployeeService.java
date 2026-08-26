package com.example.employmentmanagement.service;

import com.example.employmentmanagement.exception.DuplicateEmailException;
import com.example.employmentmanagement.exception.EmployeeNotFoundException;
import com.example.employmentmanagement.model.Employee;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class EmployeeService {

    private final ConcurrentHashMap<Long, Employee> employees = new ConcurrentHashMap<>();
    private final AtomicLong idSequence = new AtomicLong(1);

    public Employee createEmployee(Employee request) {
        String email = normalize(request.getEmail());
        ensureEmailAvailable(email, null);

        Employee employee = new Employee(
                idSequence.getAndIncrement(),
                normalize(request.getName()),
                normalize(request.getOccupation()),
                email,
                request.getYearsOfExperience());
        employees.put(employee.getId(), employee);
        return copy(employee);
    }

    public List<Employee> getAllEmployees() {
        List<Employee> result = new ArrayList<>();
        for (Employee employee : employees.values()) {
            result.add(copy(employee));
        }
        result.sort(Comparator.comparing(Employee::getId));
        return result;
    }

    public Employee getEmployeeById(Long id) {
        Employee employee = employees.get(id);
        if (employee == null) {
            throw new EmployeeNotFoundException(id);
        }
        return copy(employee);
    }

    public Employee updateEmployee(Long id, Employee request) {
        Employee existing = employees.get(id);
        if (existing == null) {
            throw new EmployeeNotFoundException(id);
        }

        String email = normalize(request.getEmail());
        ensureEmailAvailable(email, id);

        existing.setName(normalize(request.getName()));
        existing.setOccupation(normalize(request.getOccupation()));
        existing.setEmail(email);
        existing.setYearsOfExperience(request.getYearsOfExperience());
        return copy(existing);
    }

    public void deleteEmployee(Long id) {
        Employee removed = employees.remove(id);
        if (removed == null) {
            throw new EmployeeNotFoundException(id);
        }
    }

    public void clear() {
        employees.clear();
        idSequence.set(1);
    }

    private void ensureEmailAvailable(String email, Long currentId) {
        for (Employee employee : employees.values()) {
            if (currentId != null && currentId.equals(employee.getId())) {
                continue;
            }
            if (employee.getEmail().equalsIgnoreCase(email)) {
                throw new DuplicateEmailException();
            }
        }
    }

    private String normalize(String value) {
        return value == null ? null : value.trim();
    }

    private Employee copy(Employee employee) {
        return new Employee(
                employee.getId(),
                employee.getName(),
                employee.getOccupation(),
                employee.getEmail(),
                employee.getYearsOfExperience());
    }
}
