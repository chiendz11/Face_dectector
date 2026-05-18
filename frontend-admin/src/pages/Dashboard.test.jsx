import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";

import Dashboard from "./Dashboard";

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

  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "admin" } });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

  await waitFor(() => screen.getByRole("heading", { name: /new employee/i }));
}

function installCameraMock() {
  const stop = vi.fn();
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop }],
      }),
    },
  });
  Object.defineProperty(HTMLMediaElement.prototype, "srcObject", {
    configurable: true,
    get() {
      return this._srcObject;
    },
    set(value) {
      this._srcObject = value;
    },
  });
  Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
    configurable: true,
    get() {
      return 4;
    },
  });
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
    configurable: true,
    get() {
      return 640;
    },
  });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
    configurable: true,
    get() {
      return 360;
    },
  });
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() }));
  HTMLCanvasElement.prototype.toDataURL = vi.fn(() => "data:image/jpeg;base64,ZmFrZS1pbWFnZQ==");
}

describe("Dashboard sign-in", () => {
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
    await performLogin(fetchMock);

    expect(localStorage.getItem("admin_token")).toBe(TOKEN);
    const loginCall = fetchMock.mock.calls.find(([url]) => url === "/api/auth/login");
    expect(JSON.parse(loginCall[1].body)).toEqual({ username: "admin", password: "admin" });
  });

  it("shows error message when login fails", async () => {
    const fetchMock = makeFetchMock({
      "POST /api/auth/login": { status: 401, body: { detail: "Unauthorized" } },
    });
    global.fetch = fetchMock;

    render(<Dashboard />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument());
  });

  it("logs out and clears token on logout button click", async () => {
    const fetchMock = makeFetchMock(loginHandlers());
    await performLogin(fetchMock);

    fireEvent.click(screen.getByRole("button", { name: /log out/i }));

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(localStorage.getItem("admin_token")).toBeNull();
  });
});

describe("Dashboard employee list", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
  });

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
              { employee_code: "EMP-001", full_name: "Alice Nguyen", department: "IT", active: true },
              { employee_code: "EMP-002", full_name: "Bob Tran", department: null, active: true },
            ],
            total: 2,
          },
        },
      }),
    );
    await performLogin(fetchMock);

    await waitFor(() => expect(screen.getByText("EMP-001")).toBeInTheDocument());
    expect(screen.getByText("Alice Nguyen")).toBeInTheDocument();
    expect(screen.getByText("EMP-002")).toBeInTheDocument();
    expect(screen.getByText("Bob Tran")).toBeInTheDocument();
    expect(screen.getAllByText("None").length).toBeGreaterThanOrEqual(1);
  });

  it("shows stat card with active employee count", async () => {
    const fetchMock = makeFetchMock(
      loginHandlers({
        "GET /api/admin/employees": {
          status: 200,
          body: {
            items: [{ employee_code: "EMP-001", full_name: "Alice", department: "IT", active: true }],
            total: 1,
          },
        },
      }),
    );
    await performLogin(fetchMock);

    const employeesArticle = screen.getByText("Active employees").closest("article");
    await waitFor(() => expect(within(employeesArticle).getByText("1")).toBeInTheDocument());
  });
});

describe("Dashboard create employee form", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("submits POST /api/admin/employees with form values", async () => {
    let postBody;
    const fetchMock = makeFetchMock(
      loginHandlers({
        "POST /api/admin/employees": (opts) => {
          postBody = JSON.parse(opts.body);
          return {
            status: 201,
            body: { employee_code: "EMP-010", full_name: "Tran Van A", department: "Security", active: true },
          };
        },
        "GET /api/admin/employees": {
          status: 200,
          body: {
            items: [{ employee_code: "EMP-010", full_name: "Tran Van A", department: "Security", active: true }],
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

    await waitFor(() =>
      expect(screen.getAllByText(/employee EMP-010 already exists/i).length).toBeGreaterThanOrEqual(1),
    );
  });
});

describe("Dashboard enrollment sessions and employee lifecycle", () => {
  beforeEach(() => {
    localStorage.clear();
    installCameraMock();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  function makeEmployeeFetchMock(extraHandler) {
    return vi.fn(async (url, opts) => {
      if (url === "/api/auth/login") return { ok: true, status: 200, json: async () => AUTH_RESPONSE };
      if (url === "/api/admin/employees" && (!opts?.method || opts.method === "GET")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ employee_code: "EMP-100", full_name: "Nguyen Van A", department: "IT", active: true }],
            total: 1,
          }),
        };
      }
      const handled = extraHandler?.(url, opts);
      if (handled) {
        return handled;
      }
      throw new Error(`Unexpected fetch: ${opts?.method || "GET"} ${url}`);
    });
  }

  it("creates a token-bound enrollment session from the employee row", async () => {
    let capturedHeaders;
    const fetchMock = makeEmployeeFetchMock((url, opts) => {
      if (url === "/api/admin/employees/EMP-100/enrollment-sessions") {
        capturedHeaders = opts.headers;
        return {
          ok: true,
          status: 201,
          json: async () => ({
            session_id: 1,
            employee_code: "EMP-100",
            token: "session-token",
            enrollment_url: "/admin/#/enroll/session/session-token",
            expires_at: "2026-05-18T12:00:00Z",
            status: "pending",
          }),
        };
      }
      return null;
    });
    await performLogin(fetchMock);

    await waitFor(() => screen.getByText("EMP-100"));
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));

    await waitFor(() => screen.getByLabelText(/enrollment camera preview/i));
    expect(capturedHeaders.Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it("submits captured samples through the enrollment session token", async () => {
    let capturedFormData;
    let capturedHeaders;
    const fetchMock = makeEmployeeFetchMock((url, opts) => {
      if (url === "/api/admin/employees/EMP-100/enrollment-sessions") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            session_id: 1,
            employee_code: "EMP-100",
            token: "session-token",
            enrollment_url: "/admin/#/enroll/session/session-token",
            expires_at: "2026-05-18T12:00:00Z",
            status: "pending",
          }),
        };
      }
      if (url === "/api/admin/enrollment-sessions/session-token/complete") {
        capturedFormData = opts.body;
        capturedHeaders = opts.headers;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            employee_code: "EMP-100",
            enrolled: true,
            sample_count: 3,
            embedding_dimensions: 512,
            message: "Face embedding enrolled for employee EMP-100 from 3 live samples.",
          }),
        };
      }
      return null;
    });
    await performLogin(fetchMock);

    await waitFor(() => screen.getByText("EMP-100"));
    fireEvent.click(screen.getByRole("button", { name: /open camera/i }));
    const captureButton = await screen.findByRole("button", { name: /capture/i });
    await waitFor(() => expect(captureButton).not.toBeDisabled());
    fireEvent.click(captureButton);
    fireEvent.click(captureButton);
    fireEvent.click(captureButton);
    const completeButton = screen.getByRole("button", { name: /complete enrollment/i });
    await waitFor(() => expect(completeButton).not.toBeDisabled());
    fireEvent.click(completeButton);

    await waitFor(() => screen.getByText(/face embedding enrolled for employee EMP-100/i));
    expect(capturedFormData).toBeInstanceOf(FormData);
    expect(capturedHeaders).toBeUndefined();
  });

  it("updates employee profile fields", async () => {
    let patchBody;
    const fetchMock = makeEmployeeFetchMock((url, opts) => {
      if (url === "/api/admin/employees/EMP-100" && opts?.method === "PATCH") {
        patchBody = JSON.parse(opts.body);
        return {
          ok: true,
          status: 200,
          json: async () => ({ employee_code: "EMP-100", full_name: "Nguyen Van B", department: "Security", active: true }),
        };
      }
      return null;
    });
    await performLogin(fetchMock);

    await waitFor(() => screen.getByText("EMP-100"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.change(screen.getByLabelText(/full name for EMP-100/i), { target: { value: "Nguyen Van B" } });
    fireEvent.change(screen.getByLabelText(/department for EMP-100/i), { target: { value: "Security" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => screen.getByText(/employee EMP-100 updated/i));
    expect(patchBody).toEqual({ full_name: "Nguyen Van B", department: "Security" });
  });

  it("soft deletes an employee through the deactivate action", async () => {
    let deleteHeaders;
    const fetchMock = makeEmployeeFetchMock((url, opts) => {
      if (url === "/api/admin/employees/EMP-100" && opts?.method === "DELETE") {
        deleteHeaders = opts.headers;
        return { ok: true, status: 200, json: async () => ({ employee_code: "EMP-100", deleted: true }) };
      }
      return null;
    });
    await performLogin(fetchMock);

    await waitFor(() => screen.getByText("EMP-100"));
    fireEvent.click(screen.getByRole("button", { name: /deactivate/i }));

    await waitFor(() => screen.getByText(/employee EMP-100 deactivated/i));
    expect(deleteHeaders.Authorization).toBe(`Bearer ${TOKEN}`);
  });
});
