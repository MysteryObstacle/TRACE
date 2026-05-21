Construct a virtual network scenario with the following requirements (node IDs are fixed and must be used exactly):

Address planning (CIDRs are fixed and must be used exactly; all are valid and non-overlapping):
- DMZ subnet:        10.10.10.0/24
- OFFICE subnet:     10.10.20.0/24
- OT subnet:         10.10.30.0/24
- MGMT subnet:       10.10.40.0/24
- BRANCH subnet:     10.20.20.0/24
- CORE_FW transit:   10.0.0.0/30
- FW_INET transit:   10.0.0.4/30
- CORE_BRANCH transit: 10.0.0.8/30

Nodes:
- Routers: R_CORE, R_BRANCH
- Switches (each represents one L2 segment): SW_DMZ, SW_OFFICE, SW_OT, SW_MGMT, SW_CORE_FW, SW_FW_INET, SW_CORE_BRANCH, SW_BRANCH
- Computers: WEB, PC1, PC2, PLC1, ADMIN, BPC1, FIREWALL, INTERNET
  (Use type="computer" for FIREWALL and INTERNET; their functional roles are reflected by image selection.)

Link chains (must be realized by explicit port-to-port links):
- WEB  -> SW_DMZ    -> R_CORE
- PC1  -> SW_OFFICE -> R_CORE
- PC2  -> SW_OFFICE -> R_CORE
- PLC1 -> SW_OT     -> R_CORE
- ADMIN -> SW_MGMT  -> R_CORE
- R_CORE -> SW_CORE_FW -> FIREWALL
- FIREWALL -> SW_FW_INET -> INTERNET
- R_CORE -> SW_CORE_BRANCH -> R_BRANCH -> SW_BRANCH -> BPC1

Connectivity intent (topology-level):
- R_CORE provides L3 connectivity among DMZ/OFFICE/OT/MGMT.
- R_BRANCH provides L3 connectivity between BRANCH and CORE_BRANCH transit.
- Fixed IPv4 addresses must be used for all router ports and for FIREWALL and INTERNET.
- Hosts WEB/PC1/PC2/PLC1/ADMIN/BPC1 may use DHCP (port.ip="") or fixed IPs, but must remain consistent with their subnets.
- Segmentation must be preserved: do not merge any of the L2 segments/subnets.
