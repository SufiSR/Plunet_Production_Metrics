import { adminApiClient } from "@/lib/admin-api-client";

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  jest.resetAllMocks();
});

function mockFetch(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

describe("adminApiClient.login", () => {
  it("returns LoginResponse on 200", async () => {
    mockFetch(200, { role: "admin", expires_at: null });
    const res = await adminApiClient.login({ username: "admin", password: "pw" });
    expect(res.role).toBe("admin");
  });

  it("throws with detail message on 401", async () => {
    mockFetch(401, { detail: "Invalid username or password" });
    await expect(
      adminApiClient.login({ username: "bad", password: "wrong" })
    ).rejects.toThrow("Invalid username or password");
  });

  it("sends credentials: include", async () => {
    mockFetch(200, { role: "admin", expires_at: null });
    await adminApiClient.login({ username: "admin", password: "pw" });
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[1]).toMatchObject({ credentials: "include" });
  });
});

describe("adminApiClient.getConfig", () => {
  it("returns config on 200", async () => {
    const cfg = { environment: "production", gitlab_url: "https://gl.test" };
    mockFetch(200, cfg);
    const res = await adminApiClient.getConfig();
    expect(res.environment).toBe("production");
  });

  it("throws on non-200", async () => {
    mockFetch(403, { detail: "Forbidden" });
    await expect(adminApiClient.getConfig()).rejects.toThrow("Forbidden");
  });
});

describe("adminApiClient.patchConfig", () => {
  it("sends only the provided fields", async () => {
    mockFetch(200, { environment: "staging" });
    await adminApiClient.patchConfig({ environment: "staging" });
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[1].method).toBe("PATCH");
    expect(JSON.parse(call[1].body as string)).toEqual({ environment: "staging" });
  });
});

describe("adminApiClient.me", () => {
  it("returns admin role when logged in", async () => {
    mockFetch(200, { role: "admin", username: "admin" });
    const res = await adminApiClient.me();
    expect(res.role).toBe("admin");
  });

  it("returns null role when not logged in", async () => {
    mockFetch(200, { role: null, username: null });
    const res = await adminApiClient.me();
    expect(res.role).toBeNull();
  });
});

describe("adminApiClient.testWebhook", () => {
  it("posts webhook_url for test send", async () => {
    mockFetch(200, {
      delivered: true,
      effective_webhook_url: "https://hooks.example.test/ok",
      payload: { event: "SYNC_TEST" },
    });
    await adminApiClient.testWebhook({ webhook_url: "https://hooks.example.test/ok" });
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body as string)).toEqual({
      webhook_url: "https://hooks.example.test/ok",
    });
  });
});

describe("adminApiClient feature families", () => {
  it("creates a feature family", async () => {
    mockFetch(201, { family: { id: 1, name: "Invoice" }, members: [] });
    await adminApiClient.createFeatureFamily({
      name: "Invoice",
      suggestion_keywords: ["invoice"],
    });
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[0]).toContain("/admin/jira-feature-families");
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body as string)).toEqual({
      name: "Invoice",
      suggestion_keywords: ["invoice"],
    });
  });

  it("updates feature family members", async () => {
    mockFetch(200, { family: { id: 1, name: "Invoice" }, members: [] });
    await adminApiClient.putFeatureFamilyMembers(1, { feature_root_ids: [10, 11] });
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[0]).toContain("/admin/jira-feature-families/1/members");
    expect(call[1].method).toBe("PUT");
    expect(JSON.parse(call[1].body as string)).toEqual({ feature_root_ids: [10, 11] });
  });

  it("encodes suggestion ids for accept", async () => {
    mockFetch(200, { family: { id: 1, name: "Invoice" }, members: [] });
    await adminApiClient.acceptFeatureFamilySuggestion("1-10-a/b");
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[0]).toContain("/admin/jira-feature-families/suggestions/1-10-a%2Fb/accept");
    expect(call[1].method).toBe("POST");
  });
});
