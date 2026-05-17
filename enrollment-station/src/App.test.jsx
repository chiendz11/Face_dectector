import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const TOKEN = "enrollment-token";

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

beforeEach(() => {
  localStorage.clear();
  installCameraMock();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Enrollment station", () => {
  it("logs in and stores the admin token", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: TOKEN }),
    });

    render(<App />);

    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "local-admin-password" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => screen.getByRole("heading", { name: /live sample capture/i }));
    expect(localStorage.getItem("enrollment_token")).toBe(TOKEN);
  });

  it("submits captured samples to the enroll-samples endpoint", async () => {
    localStorage.setItem("enrollment_token", TOKEN);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        employee_code: "EMP-001",
        enrolled: true,
        sample_count: 3,
        message: "Face embedding enrolled for employee EMP-001 from 3 live samples.",
      }),
    });
    global.fetch = fetchMock;

    render(<App />);

    await waitFor(() => expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText(/employee code/i), { target: { value: "EMP-001" } });
    fireEvent.click(screen.getByRole("button", { name: /capture/i }));
    fireEvent.click(screen.getByRole("button", { name: /capture/i }));
    fireEvent.click(screen.getByRole("button", { name: /capture/i }));
    fireEvent.click(screen.getByRole("button", { name: /enroll face/i }));

    await waitFor(() => screen.getByText(/face embedding enrolled/i));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/employees/EMP-001/enroll-samples",
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: `Bearer ${TOKEN}` },
        body: expect.any(FormData),
      }),
    );
  });
});
