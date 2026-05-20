// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title VulnerableBank
 * @notice ⚠️ INTENTIONALLY VULNERABLE — FOR SECURITY RESEARCH & AUDITING PURPOSES ONLY
 * @dev This contract contains multiple known vulnerabilities for testing the
 *      Smart Contract Security Agent detection capabilities.
 *      DO NOT DEPLOY TO MAINNET.
 */
contract VulnerableBank {
    mapping(address => uint256) public balances;
    address public owner;
    bool public paused;

    event Deposit(address indexed user, uint256 amount);
    event Withdrawal(address indexed user, uint256 amount);

    constructor() {
        owner = msg.sender;
    }

    // ─────────────────────────────────────────────────────────────────────
    // VULNERABILITY 1: Reentrancy Attack (CRITICAL)
    // State is updated AFTER external call — allows recursive withdrawal
    // Fix: Update balances[msg.sender] = 0 BEFORE the external call
    // ─────────────────────────────────────────────────────────────────────
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");

        // ❌ External call before state update — classic reentrancy vector
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        // ❌ State update happens AFTER the external call
        balances[msg.sender] -= amount;

        emit Withdrawal(msg.sender, amount);
    }

    // ─────────────────────────────────────────────────────────────────────
    // VULNERABILITY 2: Missing Access Control (HIGH)
    // Any address can call emergencyWithdraw, not just the owner
    // Fix: Add onlyOwner modifier
    // ─────────────────────────────────────────────────────────────────────
    function emergencyWithdraw() public {
        // ❌ No access control — anyone can drain the contract
        uint256 contractBalance = address(this).balance;
        payable(msg.sender).transfer(contractBalance);
    }

    // ─────────────────────────────────────────────────────────────────────
    // VULNERABILITY 3: Integer Overflow Risk (MEDIUM)
    // Pre-0.8.0 style unchecked arithmetic — dangerous in older contracts
    // Note: Solidity 0.8+ reverts by default, but explicit unchecked blocks
    // can still introduce this vulnerability
    // ─────────────────────────────────────────────────────────────────────
    function addToBalance(address user, uint256 amount) public {
        unchecked {
            // ❌ Unchecked addition — can overflow
            balances[user] += amount;
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // VULNERABILITY 4: Unchecked Return Value (MEDIUM)
    // transfer() return value not checked — silent failures
    // Fix: Use call{value:}("") and check return value
    // ─────────────────────────────────────────────────────────────────────
    function sendReward(address recipient, uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        balances[msg.sender] -= amount;
        // ❌ transfer() return value is not checked
        payable(recipient).transfer(amount);
    }

    // ─────────────────────────────────────────────────────────────────────
    // VULNERABILITY 5: Timestamp Dependence (LOW)
    // Miners can manipulate block.timestamp within ~15 seconds
    // Fix: Avoid using timestamp for critical randomness or time gates
    // ─────────────────────────────────────────────────────────────────────
    function timeLimitedAction() public view returns (bool) {
        // ❌ block.timestamp is manipulable by miners
        return block.timestamp % 2 == 0;
    }

    // ─────────────────────────────────────────────────────────────────────
    // Safe functions (for comparison)
    // ─────────────────────────────────────────────────────────────────────
    function deposit() public payable {
        balances[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    function getBalance() public view returns (uint256) {
        return balances[msg.sender];
    }

    receive() external payable {}
}
