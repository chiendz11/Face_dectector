import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";

import Dashboard from "./Dashboard";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFetchMock(handlers) {
  return vi.fn(async (url, opts) => {
    const key = `${(opts?.method || "GET").toUpperCase()} ${url}`;
    const handler = handlers[key];
    if (!handler) {
      throw new Error(`Unexpected fetch: ${key}`);
    }
    const { status = 200, body } = typeof handler === "function" ? handler(opts) : handler;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  });
}

const TOKEN = "test-jwt-token";
const AUTH_RESPONSE = { access_token: TOKEN };

function loginHandlers(extra = {}) {
  return {
    "POST /api/auth/login": { status: 200, body: AUTH_RESPONSE },
    "GET /api/admin/employees": { status: 200, body: { items: [], total: 0 } },
    ...extra,
  };
}

async function performLogin(fetchMock) {
  global.fetch = fetchMock;

  render(<Dashboard />);

  fireEvent.change(screen.getByLabelText(/username/i), {
    target: { value: "admin" },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: "admin" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

  await waitFor(() => screen.getByRole("heading", { name: /new employee/i }));
}

// ---------------------------------------------------------------------------
// Tests: login / auth
// ---------------------------------------------------------------------------

describe("Dashboard — sign-in form", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders sign-in form when no token is stored", () => {
    render(<Dashboard />);
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls POST /api/auth/login and stores token on success", async () => {
    const fetchMock = makeFetchMock(loginHandlers());
    global.fetch = fetchMock;

    render(<Dashboard />);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => screen.getByRole("heading", { name: /new employee/i }));

    expect(localStorage.getItem("admin_token")).toBe(TOKEN);
    const loginCall = fetchMock.mock.calls.find(([url]) => url === "/api/auth/login");
    expect(loginCall).toBeDefined();
    const body = JSON.parse(loginCall[1].body);
    expect(body).toEqual({ username: "admin", password: "admin" });
  });

  it("shows error message when login fails", async () => {
    const fetchMock = makeFetchMock({
      "POST /api/auth/login": { status: 401, body: { detail: "Unauthorized" } },
    });
    global.fetch = fetchMock;

    render(<Dashboard />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument(),
    );
  });

  it("logs out and clears token on logout button click", async () => {
    const fetchMock = makeFetchMock(loginHandlers());
    await performLogin(fetchMock);

    fireEvent.click(screen.getByRole("button", { name: /log out/i }));

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(localStorage.getItem("admin_token")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests: employee list
// ---------------------------------------------------------------------------

describe("Dashboard — employee list", () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

  it("shows empty state message when no employees registered", async () => {
    const fetchMock = makeFetchMock(loginHandlers());
    await performLogin(fetchMock);

    expect(screen.getByText(/no employees registered yet/i)).toBeInTheDocument();
  });

  it("renders employee rows after login", async () => {
    const fetchMock = makeFetchMock(
      loginHandlers({
        "GET /api/admin/employees": {
          status: 200,
          body: {
            items: [
              { employee_code: "EMP-001", full_name: "Alice Nguyen", department: "IT" },
              { employee_code: "EMP-002", full_name: "Bob Tran", department: null },
            ],
            total: 2,
          },
        },
      }),
    );
    await performLogin(fetchMock);

    expect(screen.getByText("EMP-001")).toBeInTheDocument();
    expect(screen.getByText("Alice Nguyen")).toBeInTheDocument();
    expect(screen.getByText("EMP-002")).toBeInTheDocument();
    expect(screen.getByText("Bob Tran")).toBeInTheDocument();
    // null department falls back to "—"
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("shows stat card with enrolled employee count", async () => {
    const fetchMock = makeFetchMock(
      loginHandlers({
        "GET /api/admin/employees": {
          status: 200,
          body: {
            items: [{ employee_code: "EMP-001", full_name: "Alice", department: "IT" }],
            total: 1,
          },
        },
      }),
    );
    await performLogin(fetchMock);

    // StatCard for employee count should show "1" — use within() to scope to Employees article
    const employeesArticle = screen.getByText("Employees").closest("article");
    expect(within(employeesArticle).getByText("1")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests: create employee form
// ---------------------------------------------------------------------------

describe("Dashboard — create employee form", () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

  it("submits POST /api/admin/employees with form values", async () => {
    let postBody;
    const fetchMock = makeFetchMock(
      loginHandlers({
        "POST /api/admin/employees": (opts) => {
          postBody = JSON.parse(opts.body);
          return {
            status: 201,
            body: { employee_code: "EMP-010", full_name: "Tran Van A", department: "Security" },
          };
        },
        "GET /api/admin/employees": {
          status: 200,
          body: {
            items: [{ employee_code: "EMP-010", full_name: "Tran Van A", department: "Security" }],
            total: 1,
          },
        },
      }),
    );
    await performLogin(fetchMock);

    fireEvent.change(screen.getByLabelText(/employee code/i), { target: { value: "EMP-010" } });
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Tran Van A" } });
    fireEvent.change(screen.getByLabelText(/department/i), { target: { value: "Security" } });
    fireEvent.click(screen.getByRole("button", { name: /add employee/i }));

    await waitFor(() => expect(screen.getByText("EMP-010")).toBeInTheDocument());

    expect(postBody).toEqual({ employee_code: "EMP-010", full_name: "Tran Van A", department: "Security" });
  });

  it("shows error when create employee returns 409", async () => {
    const fetchMock = makeFetchMock(
      loginHandlers({
        "POST /api/admin/employees": {
          status: 409,
          body: { detail: "employee EMP-010 already exists" },
        },
      }),
    );
    await performLogin(fetchMock);

    fireEvent.change(screen.getByLabelText(/employee code/i), { target: { value: "EMP-010" } });
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Duplicate" } });
    fireEvent.click(screen.getByRole("button", { name: /add employee/i }));

    // error shown in 2 places (create form + table section) — check at least one exists
    await waitFor(() =>
      expect(screen.getAllByText(/employee EMP-010 already exists/i).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("clears form fields after successful create", async () => {
    const fetchMock = makeFetchMock(
      loginHandlers({
        "POST /api/admin/employees": {
          status: 201,
          body: { employee_code: "EMP-011", full_name: "Le Thi B", department: null },
        },
        "GET /api/admin/employees": {
          status: 200,
          body: { items: [{ employee_code: "EMP-011", full_name: "Le Thi B", department: null }], total: 1 },
        },
      }),
    );
    await performLogin(fetchMock);

    const codeInput = screen.getByLabelText(/employee code/i);
    fireEvent.change(codeInput, { target: { value: "EMP-011" } });
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Le Thi B" } });
    fireEvent.click(screen.getByRole("button", { name: /add employee/i }));

    await waitFor(() => expect(codeInput.value).toBe(""));
  });
});

// ---------------------------------------------------------------------------
// Tests: enroll face flow (new feature)
// ---------------------------------------------------------------------------

describe("Dashboard — enroll face upload", () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

  async function loginWithOneEmployee(fetchMock, extraHandlers = {}) {
    const handlers = loginHandlers({
      "GET /api/admin/employees": {
        status: 200,
        body: {
          items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT" }],
          total: 1,
        },
      },
      ...extraHandlers,
    });
    global.fetch = vi.fn(async (url, opts) => {
      const key = `${(opts?.method || "GET").toUpperCase()} ${url}`;
      const handler = handlers[key];
      if (!handler) throw new Error(`Unexpected fetch: ${key}`);
      const { status = 200, body } = typeof handler === "function" ? handler(opts) : handler;
      return { ok: status >= 200 && status < 300, status, json: async () => body };
    });
    await performLogin(global.fetch);
  }

  it("renders Enroll button for each employee row", async () => {
    await loginWithOneEmployee(null);
    const enrollButtons = screen.getAllByRole("button", { name: /enroll/i });
    expect(enrollButtons.length).toBe(1);
  });

  it("renders file input for each employee row", async () => {
    await loginWithOneEmployee(null);
    const fileInputs = document.querySelectorAll("input[type=file]");
    expect(fileInputs.length).toBe(1);
  });

  it("shows error when Enroll clicked without selecting a file", async () => {
    await loginWithOneEmployee(null);
    fireEvent.click(screen.getByRole("button", { name: /enroll/i }));

    // error shown in 2 places — check at least one exists
    await waitFor(() =>
      expect(screen.getAllByText(/please select an image file before enrolling/i).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("calls POST /api/admin/employees/{code}/enroll with FormData on submit", async () => {
    let capturedFormData;
    const fetchMock = vi.fn(async (url, opts) => {
      if (url === "/api/auth/login") {
        return { ok: true, status: 200, json: async () => AUTH_RESPONSE };
      }
      if (url === "/api/admin/employees" && (!opts?.method || opts.method === "GET")) {
        return {
          ok: true, status: 200,
          json: async () => ({
            items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT" }],
            total: 1,
          }),
        };
      }
      if (url === "/api/admin/employees/EMP-100/enroll" && opts?.method === "POST") {
        capturedFormData = opts.body;
        return {
          ok: true, status: 200,
          json: async () => ({
            employee_code: "EMP-100",
            enrolled: true,
            embedding_dimensions: 16,
            message: "Face embedding enrolled for employee EMP-100.",
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${opts?.method} ${url}`);
    });
    global.fetch = fetchMock;

    await performLogin(fetchMock);

    const fakeFile = new File(["face-data"], "photo.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector("input[type=file]");
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });
    fireEvent.click(screen.getByRole("button", { name: /enroll/i }));

    await waitFor(() =>
      expect(screen.getByText(/face embedding enrolled for employee EMP-100/i)).toBeInTheDocument(),
    );

    expect(capturedFormData).toBeInstanceOf(FormData);
  });

  it("shows success message after successful enroll", async () => {
    const fetchMock = vi.fn(async (url, opts) => {
      if (url === "/api/auth/login") return { ok: true, status: 200, json: async () => AUTH_RESPONSE };
      if (url === "/api/admin/employees" && (!opts?.method || opts.method === "GET")) {
        return {
          ok: true, status: 200,
          json: async () => ({
            items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT" }],
            total: 1,
          }),
        };
      }
      if (url === "/api/admin/employees/EMP-100/enroll") {
        return {
          ok: true, status: 200,
          json: async () => ({
            employee_code: "EMP-100",
            enrolled: true,
            embedding_dimensions: 16,
            message: "Face embedding enrolled for employee EMP-100.",
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${opts?.method} ${url}`);
    });
    global.fetch = fetchMock;
    await performLogin(fetchMock);

    const fakeFile = new File(["face-data"], "photo.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector("input[type=file]");
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });
    fireEvent.click(screen.getByRole("button", { name: /enroll/i }));

    await waitFor(() =>
      expect(screen.getByText(/face embedding enrolled for employee EMP-100/i)).toBeInTheDocument(),
    );
  });

  it("shows error message when enroll API returns error", async () => {
    const fetchMock = vi.fn(async (url, opts) => {
      if (url === "/api/auth/login") return { ok: true, status: 200, json: async () => AUTH_RESPONSE };
      if (url === "/api/admin/employees" && (!opts?.method || opts.method === "GET")) {
        return {
          ok: true, status: 200,
          json: async () => ({
            items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT" }],
            total: 1,
          }),
        };
      }
      if (url === "/api/admin/employees/EMP-100/enroll") {
        return {
          ok: false, status: 404,
          json: async () => ({ detail: "employee EMP-100 was not found" }),
        };
      }
      throw new Error(`Unexpected fetch: ${opts?.method} ${url}`);
    });
    global.fetch = fetchMock;
    await performLogin(fetchMock);

    const fakeFile = new File(["face-data"], "photo.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector("input[type=file]");
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });
    fireEvent.click(screen.getByRole("button", { name: /enroll/i }));

    // error shown in 2 places — check at least one exists
    await waitFor(() =>
      expect(screen.getAllByText(/employee EMP-100 was not found/i).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("sends Authorization header with JWT token on enroll request", async () => {
    let capturedHeaders;
    const fetchMock = vi.fn(async (url, opts) => {
      if (url === "/api/auth/login") return { ok: true, status: 200, json: async () => AUTH_RESPONSE };
      if (url === "/api/admin/employees" && (!opts?.method || opts.method === "GET")) {
        return {
          ok: true, status: 200,
          json: async () => ({
            items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT" }],
            total: 1,
          }),
        };
      }
      if (url === "/api/admin/employees/EMP-100/enroll") {
        capturedHeaders = opts.headers;
        return {
          ok: true, status: 200,
          json: async () => ({
            employee_code: "EMP-100",
            enrolled: true,
            embedding_dimensions: 16,
            message: "Face embedding enrolled for employee EMP-100.",
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${opts?.method} ${url}`);
    });
    global.fetch = fetchMock;
    await performLogin(fetchMock);

    const fakeFile = new File(["face-data"], "photo.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector("input[type=file]");
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });
    fireEvent.click(screen.getByRole("button", { name: /enroll/i }));

    await waitFor(() =>
      expect(screen.getByText(/face embedding enrolled/i)).toBeInTheDocument(),
    );

    expect(capturedHeaders?.Authorization).toBe(`Bearer ${TOKEN}`);
  });
});
