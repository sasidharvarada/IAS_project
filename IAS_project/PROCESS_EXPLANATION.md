### **Master Node (192.168.1.10)**

Based on `infra/platform_config.yaml`, the master node primarily runs core platform services and management components.

*   **Nginx (1-2 processes, depending on configuration):** Acts as the primary load balancer and API gateway for incoming requests to the platform. Routes requests to appropriate services or application instances.
*   **Kafka Broker (1 process):** Message broker for inter-service communication within the platform (e.g., deployment events, health checks, logging).
*   **Zookeeper (1 process):** Manages coordination and configuration for Kafka and other distributed services.
*   **Lifecycle Manager (1 process):** Manages the lifecycle of applications and instances, including deployment, scaling, and termination.
*   **VM Health Checker (1 process):** Monitors the health and resource utilization of all worker VMs (VM1, VM2, etc.).
*   **App Deployer (1 process):** Orchestrates the deployment of applications to worker VMs, using `deployer.py` and `process_manager.py` internally.
*   **Gateway API (1 process):** The main API endpoint for the platform, handling requests from users/CLI for application management.

```mermaid
graph TD
    subgraph Master Node (192.168.1.10)
        Nginx["Nginx (Load Balancer)"]
        Kafka["Kafka Broker"]
        Zookeeper["Zookeeper"]
        LCM["Lifecycle Manager"]
        VMHC["VM Health Checker"]
        AppDeployer["App Deployer"]
        GatewayAPI["Gateway API"]
    end
    Nginx --> GatewayAPI
    AppDeployer --> LCM
    VMHC --> LCM
    LCM <--> Kafka
    Kafka <--> Zookeeper
```

---

### **Worker VM1 (192.168.1.11)**

Based on `infra/platform_config.yaml` and `storage/apps/email_classifier/instances/instance_001.yaml`, VM1 hosts parts of `email-classifier-agent` instance `instance-001`.

*   **Platform Agent (1 process):** A small agent installed by the platform to manage local processes, collect metrics, and communicate with the Lifecycle Manager on the master node.
*   **`email-classifier-agent_instance-001_email-llm-model` (1 process, port 8001):** The LLM model component for `instance-001` of the `email-classifier-agent`.
*   **`email-classifier-agent_instance-001_classifier-agent` (1-2 processes, port 8003, scaled as per `load_config.yaml`):** The main agent for `instance-001` of the `email-classifier-agent`. This process can scale up to 2 replicas as per the load settings for this specific artifact.
*   **`email-classifier-agent_instance-001_email-orchestrator` (1 process, port 8004):** The orchestrator component for `instance-001` of the `email-classifier-agent`.

```mermaid
graph TD
    subgraph Worker VM1 (192.168.1.11)
        PA1["Platform Agent"]
        EC_LLM_M1["email-classifier-agent_instance-001_email-llm-model (Port 8001)"]
        EC_CA1["email-classifier-agent_instance-001_classifier-agent (Port 8003)"]
        EC_ORC1["email-classifier-agent_instance-001_email-orchestrator (Port 8004)"]
    end
    PA1 -- Reports Health --> Master Node
    EC_CA1 -- Calls --> EC_LLM_M1
    EC_ORC1 -- Orchestrates --> EC_CA1
```

---

### **Worker VM2 (192.168.1.12)**

Based on `infra/platform_config.yaml` and `storage/apps/email_classifier/instances/instance_001.yaml`, VM2 hosts another part of `email-classifier-agent` instance `instance-001`.

*   **Platform Agent (1 process):** A small agent installed by the platform to manage local processes, collect metrics, and communicate with the Lifecycle Manager on the master node.
*   **`email-classifier-agent_instance-001_text-simplifier-tool` (1 process, port 8002):** The text simplifier tool component for `instance-001` of the `email-classifier-agent`.

```mermaid
graph TD
    subgraph Worker VM2 (192.168.1.12)
        PA2["Platform Agent"]
        EC_TS_T1["email-classifier-agent_instance-001_text-simplifier-tool (Port 8002)"]
    end
    PA2 -- Reports Health --> Master Node
```

---

**Interaction Flow:**

1.  User sends a request to the `Gateway API` on the `Master Node`.
2.  `Nginx` on the `Master Node` load balances and forwards the request to the `Gateway API`.
3.  The `Gateway API` consults the `Lifecycle Manager` to find the available `email-orchestrator` instances for `email-classifier-agent_instance-001`.
4.  The request is routed to an `email-orchestrator` process (e.g., on VM1).
5.  The `email-orchestrator` on VM1 interacts with the `classifier-agent` on VM1 and the `email-llm-model` on VM1. It might also use the `text-simplifier-tool` on VM2.
6.  `Platform Agents` on VM1 and VM2 continuously report health and metrics to the `VM Health Checker` and `Lifecycle Manager` on the `Master Node` via `Kafka`.
7.  Based on `load_config.yaml` and reported metrics, the `Lifecycle Manager` might instruct `App Deployer` to scale up/down `classifier-agent` instances on VM1 (or other worker VMs as configured).