import requests
import json

# Sample epochs across time: 2023 through now
# Solana epochs are roughly every 2-3 days
# Epoch ~400 = early 2023, ~600 = mid 2024, ~800 = early 2025, ~950 = now
test_epochs = [400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 945, 948]

results = []

for epoch in test_epochs:
    try:
        # Get network MEV total
        mev_r = requests.post(
            "https://kobe.mainnet.jito.network/api/v1/mev_rewards",
            json={"epoch": epoch},
            headers={"Content-Type": "application/json"},
        )
        mev_data = mev_r.json()

        # Get validator count
        val_r = requests.post(
            "https://kobe.mainnet.jito.network/api/v1/jitosol_validators",
            json={"epoch": epoch},
            headers={"Content-Type": "application/json"},
        )
        val_data = val_r.json()
        num_validators = len(val_data["validators"])

        total_mev_sol = round(mev_data["total_network_mev_lamports"] / 1e9, 2)

        results.append({
            "epoch": epoch,
            "total_mev_sol": total_mev_sol,
            "jito_validators": num_validators,
        })

        print(f"Epoch {epoch}: {total_mev_sol} SOL MEV, {num_validators} Jito validators")

    except Exception as e:
        print(f"Epoch {epoch}: Error - {e}")

print("\n--- Summary ---")
for r in results:
    print(f"Epoch {r['epoch']}: {r['total_mev_sol']:>10} SOL MEV | {r['jito_validators']} validators")
