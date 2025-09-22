# recruitee-mcp

## Kubernetes deployment

The repository contains example manifests under `k8s/` for running the HTTP
server on Kubernetes.

1. Deploy the application pods:
   ```bash
   kubectl apply -f k8s/deployment.yaml
   ```
2. Expose the pods internally through a ClusterIP Service:
   ```bash
   kubectl apply -f k8s/service.yaml
   ```
3. Publish the Service externally with an Ingress resource:
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```

Update the container image in `k8s/deployment.yaml` to match the image you wish
to deploy. The Service exposes port 80 inside the cluster and forwards traffic
to the container port `8080` declared in the Deployment.

The default Ingress manifest assumes an ingress controller such as NGINX. Adjust
the annotations under `metadata.annotations` to match your ingress controller
(e.g., `kubernetes.io/ingress.class`, `nginx.ingress.kubernetes.io/rewrite-target`).
Set `external-dns.alpha.kubernetes.io/hostname` (or controller-specific
equivalents) and the `spec.rules[0].host` value to the hostname that should
route to this service. To enable TLS termination, provide a TLS secret name in
the `spec.tls` section and, if using cert-manager, uncomment the
`cert-manager.io/cluster-issuer` annotation or replace it with the issuer name
required by your environment.

Once the manifests are configured, you can apply updates at any time with
`kubectl apply -f k8s/` to sync all resources in a single command.
