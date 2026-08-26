package com.example.employmentmanagement.exception;

public class DuplicateEmailException extends RuntimeException {

    public DuplicateEmailException() {
        super("An employee with this email already exists");
    }
}
