const API_BASE_URL = "/api/employees";

const form = document.getElementById("employee-form");
const formTitle = document.getElementById("form-title");
const submitButton = document.getElementById("submit-button");
const clearButton = document.getElementById("clear-button");
const cancelEditButton = document.getElementById("cancel-edit-button");
const searchInput = document.getElementById("search");
const tbody = document.getElementById("employee-tbody");
const tableWrap = document.getElementById("table-wrap");
const emptyState = document.getElementById("empty-state");
const loading = document.getElementById("loading");
const apiStatus = document.getElementById("api-status");
const apiStatusText = document.getElementById("api-status-text");
const statTotal = document.getElementById("stat-total");
const statAverage = document.getElementById("stat-average");
const modal = document.getElementById("modal");
const modalMessage = document.getElementById("modal-message");
const modalCancel = document.getElementById("modal-cancel");
const modalConfirm = document.getElementById("modal-confirm");
const emptyAddButton = document.getElementById("empty-add-button");
const toasts = document.getElementById("toasts");

let employees = [];
let editingId = null;
let pendingDelete = null;
let activeRequests = 0;

function setLoading(isLoading) {
    if (isLoading) {
        activeRequests += 1;
    } else {
        activeRequests = Math.max(0, activeRequests - 1);
    }
    loading.classList.toggle("hidden", activeRequests === 0);
}

function setApiStatus(connected) {
    apiStatus.classList.toggle("connected", connected);
    apiStatus.classList.toggle("disconnected", !connected);
    apiStatusText.textContent = connected ? "API Connected" : "API Disconnected";
}

function showToast(message, type) {
    const toast = document.createElement("div");
    toast.className = "toast " + type;
    toast.textContent = message;
    toasts.appendChild(toast);
    setTimeout(function () {
        toast.remove();
    }, 3500);
}

function formatExperience(years) {
    return years === 1 ? "1 Year" : years + " Years";
}

function updateStatistics() {
    statTotal.textContent = String(employees.length);
    if (employees.length === 0) {
        statAverage.textContent = "0 Years";
        return;
    }
    const totalYears = employees.reduce(function (sum, employee) {
        return sum + Number(employee.yearsOfExperience || 0);
    }, 0);
    const average = totalYears / employees.length;
    statAverage.textContent = average.toFixed(1) + " Years";
}

function matchesSearch(employee, query) {
    if (!query) {
        return true;
    }
    const haystack = [employee.name, employee.occupation, employee.email].join(" ").toLowerCase();
    return haystack.includes(query);
}

function renderTable() {
    const query = searchInput.value.trim().toLowerCase();
    const visible = employees.filter(function (employee) {
        return matchesSearch(employee, query);
    });

    tbody.replaceChildren();

    if (employees.length === 0) {
        emptyState.classList.remove("hidden");
        tableWrap.classList.add("hidden");
        return;
    }

    emptyState.classList.add("hidden");
    tableWrap.classList.remove("hidden");

    visible.forEach(function (employee) {
        const row = document.createElement("tr");

        const idCell = document.createElement("td");
        idCell.textContent = String(employee.id);
        row.appendChild(idCell);

        const nameCell = document.createElement("td");
        nameCell.textContent = employee.name;
        row.appendChild(nameCell);

        const occupationCell = document.createElement("td");
        occupationCell.textContent = employee.occupation;
        row.appendChild(occupationCell);

        const emailCell = document.createElement("td");
        emailCell.textContent = employee.email;
        row.appendChild(emailCell);

        const experienceCell = document.createElement("td");
        experienceCell.textContent = formatExperience(employee.yearsOfExperience);
        row.appendChild(experienceCell);

        const actionsCell = document.createElement("td");
        const actions = document.createElement("div");
        actions.className = "row-actions";

        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "btn btn-secondary btn-small";
        editButton.textContent = "Edit";
        editButton.addEventListener("click", function () {
            enterEditMode(employee);
        });

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "btn btn-danger btn-small";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", function () {
            openDeleteModal(employee);
        });

        actions.appendChild(editButton);
        actions.appendChild(deleteButton);
        actionsCell.appendChild(actions);
        row.appendChild(actionsCell);
        tbody.appendChild(row);
    });
}

function resetForm() {
    form.reset();
    editingId = null;
    formTitle.textContent = "Add Employee";
    submitButton.textContent = "Add Employee";
    cancelEditButton.classList.add("hidden");
}

function enterEditMode(employee) {
    editingId = employee.id;
    document.getElementById("name").value = employee.name;
    document.getElementById("occupation").value = employee.occupation;
    document.getElementById("email").value = employee.email;
    document.getElementById("yearsOfExperience").value = employee.yearsOfExperience;
    formTitle.textContent = "Edit Employee";
    submitButton.textContent = "Update Employee";
    cancelEditButton.classList.remove("hidden");
    document.getElementById("name").focus();
}

function openDeleteModal(employee) {
    pendingDelete = employee;
    modalMessage.textContent = 'Are you sure you want to delete "' + employee.name + '"?';
    modal.classList.remove("hidden");
}

function closeDeleteModal() {
    pendingDelete = null;
    modal.classList.add("hidden");
}

async function apiRequest(path, options) {
    setLoading(true);
    try {
        const response = await fetch(API_BASE_URL + path, options);
        setApiStatus(true);
        return response;
    } catch (error) {
        setApiStatus(false);
        showToast("⚠ Unable to connect to the API", "error");
        throw error;
    } finally {
        setLoading(false);
    }
}

async function readErrorMessage(response) {
    try {
        const body = await response.json();
        if (body && body.message) {
            return body.message;
        }
        if (body && body.errors && body.errors.email) {
            return "⚠ Please enter a valid email address";
        }
    } catch (error) {
        return "Request failed";
    }
    return "Request failed";
}

async function loadEmployees() {
    try {
        const response = await apiRequest("", { method: "GET" });
        if (!response.ok) {
            showToast("⚠ Unable to load employees", "error");
            return;
        }
        employees = await response.json();
        updateStatistics();
        renderTable();
    } catch (error) {
        employees = [];
        updateStatistics();
        renderTable();
    }
}

function getFormPayload() {
    return {
        name: document.getElementById("name").value.trim(),
        occupation: document.getElementById("occupation").value.trim(),
        email: document.getElementById("email").value.trim(),
        yearsOfExperience: Number(document.getElementById("yearsOfExperience").value)
    };
}

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const payload = getFormPayload();
    const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

    if (!payload.name || !payload.occupation || !payload.email || Number.isNaN(payload.yearsOfExperience)) {
        showToast("⚠ Please complete all required fields", "error");
        return;
    }
    if (!emailPattern.test(payload.email)) {
        showToast("⚠ Please enter a valid email address", "error");
        return;
    }

    const isEdit = editingId !== null;
    try {
        const response = await apiRequest(isEdit ? "/" + editingId : "", {
            method: isEdit ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (response.status === 404) {
            showToast("⚠ Employee not found", "error");
            return;
        }
        if (!response.ok) {
            const message = await readErrorMessage(response);
            if (message.toLowerCase().indexOf("email") !== -1 && message.toLowerCase().indexOf("valid") !== -1) {
                showToast("⚠ Please enter a valid email address", "error");
            } else {
                showToast("⚠ " + message, "error");
            }
            return;
        }

        resetForm();
        await loadEmployees();
        showToast(isEdit ? "✓ Employee updated successfully" : "✓ Employee added successfully", "success");
    } catch (error) {
        return;
    }
});

clearButton.addEventListener("click", function () {
    resetForm();
});

cancelEditButton.addEventListener("click", function () {
    resetForm();
});

searchInput.addEventListener("input", function () {
    renderTable();
});

emptyAddButton.addEventListener("click", function () {
    document.getElementById("name").focus();
});

modalCancel.addEventListener("click", function () {
    closeDeleteModal();
});

modalConfirm.addEventListener("click", async function () {
    if (!pendingDelete) {
        return;
    }
    const id = pendingDelete.id;
    closeDeleteModal();
    try {
        const response = await apiRequest("/" + id, { method: "DELETE" });
        if (response.status === 404) {
            showToast("⚠ Employee not found", "error");
            return;
        }
        if (!response.ok) {
            showToast("⚠ " + await readErrorMessage(response), "error");
            return;
        }
        if (editingId === id) {
            resetForm();
        }
        await loadEmployees();
        showToast("✓ Employee deleted successfully", "success");
    } catch (error) {
        return;
    }
});

loadEmployees();
setInterval(function () {
    fetch(API_BASE_URL)
        .then(function (response) {
            setApiStatus(response.ok);
        })
        .catch(function () {
            setApiStatus(false);
        });
}, 15000);
